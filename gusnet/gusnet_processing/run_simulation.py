"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsProcessingUtils,
    QgsProject,
)
from qgis.PyQt.QtCore import QCoreApplication, QThread
from qgis.PyQt.QtGui import QIcon

import gusnet
from gusnet.elements import DemandType, FlowUnit, HeadlossFormula, ModelLayer, ResultLayer
from gusnet.gusnet_processing.common import CommonProcessingBase, profile
from gusnet.i18n import tr
from gusnet.interface import NetworkModelError, Writer, check_network, describe_network, describe_pipes
from gusnet.settings import ProjectSettings, SettingKey
from gusnet.style import style
from gusnet.units import SpecificUnitNames

if TYPE_CHECKING:
    import wntr


class _ModelCreatorAlgorithm(CommonProcessingBase):
    UNITS = "UNITS"
    DURATION = "DURATION"
    HEADLOSS_FORMULA = "HEADLOSS_FORMULA"
    OUTPUT_INP = "OUTPUT_INP"
    DEMAND_TYPE = "DEMAND_TYPE"

    def initAlgorithm(self, config=None):  # noqa N802
        self.init_input_parameters()
        self.init_output_parameters()

    def init_input_parameters(self):
        project_settings = ProjectSettings(QgsProject.instance())

        default_layers = project_settings.get(SettingKey.MODEL_LAYERS, {})
        for lyr in ModelLayer:
            param = QgsProcessingParameterFeatureSource(
                lyr.name,
                lyr.friendly_name,
                types=lyr.acceptable_processing_vectors,
                optional=lyr is not ModelLayer.JUNCTIONS,
            )
            savedlyr = default_layers.get(lyr.name)
            if savedlyr and param.checkValueIsAcceptable(savedlyr) and QgsProject.instance().mapLayer(savedlyr):
                param.setGuiDefaultValueOverride(savedlyr)

            self.addParameter(param)

        param = QgsProcessingParameterEnum(
            self.UNITS,
            tr("Units"),
            options=[fu.friendly_name for fu in FlowUnit],
            allowMultiple=False,
            usesStaticStrings=False,
        )
        default_flow_units = project_settings.get(SettingKey.FLOW_UNITS)
        param.setGuiDefaultValueOverride(list(FlowUnit).index(default_flow_units) if default_flow_units else None)
        self.addParameter(param)

        param = QgsProcessingParameterEnum(
            self.HEADLOSS_FORMULA,
            tr("Headloss Formula"),
            options=[formula.friendly_name for formula in HeadlossFormula],
            allowMultiple=False,
            usesStaticStrings=False,
        )
        default_hl_formula = project_settings.get(SettingKey.HEADLOSS_FORMULA)
        param.setGuiDefaultValueOverride(
            list(HeadlossFormula).index(default_hl_formula) if default_hl_formula else None
        )
        self.addParameter(param)

        param = QgsProcessingParameterNumber(
            self.DURATION, tr("Simulation duration in hours (or 0 for single period)"), minValue=0
        )
        param.setGuiDefaultValueOverride(project_settings.get(SettingKey.SIMULATION_DURATION, 0))
        self.addParameter(param)

        param = QgsProcessingParameterEnum(
            self.DEMAND_TYPE,
            tr("Demand Type"),
            options=[option.friendly_name for option in DemandType],
            allowMultiple=False,
            usesStaticStrings=False,
            defaultValue=0,
        )
        default_demand_type = project_settings.get(SettingKey.DEMAND_TYPE)
        param.setGuiDefaultValueOverride(list(DemandType).index(default_demand_type) if default_demand_type else None)
        self.addParameter(param)

    def init_output_parameters(self):
        pass

    def init_output_files_parameters(self):
        self.addParameter(
            QgsProcessingParameterFeatureSink(ResultLayer.NODES.results_name, tr("Simulation Results - Nodes"))
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(ResultLayer.LINKS.results_name, tr("Simulation Results - Links"))
        )

    def init_export_inp_parameter(self):
        self.addParameter(
            QgsProcessingParameterFileDestination(self.OUTPUT_INP, tr("Output .inp file"), fileFilter="*.inp")
        )

    def _get_flow_unit(self, parameters: dict[str, Any], context: QgsProcessingContext) -> FlowUnit:
        """
        Get the flow unit from the parameters.
        """
        flow_unit_index = self.parameterAsEnum(parameters, self.UNITS, context)
        return list(FlowUnit)[flow_unit_index]

    def _get_headloss_formula(self, parameters: dict[str, Any], context: QgsProcessingContext) -> HeadlossFormula:
        """
        Get the headloss formula from the parameters.
        """
        headloss_formula_index = self.parameterAsEnum(parameters, self.HEADLOSS_FORMULA, context)
        return list(HeadlossFormula)[headloss_formula_index]

    def _get_demand_type(self, parameters: dict[str, Any], context: QgsProcessingContext) -> DemandType:
        """
        Get the demand type from the parameters.
        """
        demand_type_index = self.parameterAsEnum(parameters, self.DEMAND_TYPE, context)
        return list(DemandType)[demand_type_index]

    def _get_duration(self, parameters: dict[str, Any], context: QgsProcessingContext) -> float:
        """
        Get the simulation duration from the parameters.
        """

        return self.parameterAsDouble(parameters, self.DURATION, context)

    def _get_crs(self, parameters: dict[str, Any], context: QgsProcessingContext) -> QgsCoordinateReferenceSystem:
        junction_source = self.parameterAsSource(parameters, ModelLayer.JUNCTIONS.name, context)
        return junction_source.sourceCrs()

    def _get_wn(
        self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback
    ) -> wntr.network.WaterNetworkModel:
        flow_unit = self._get_flow_unit(parameters, context)

        headloss = self._get_headloss_formula(parameters, context).value

        sources = {lyr.name: self.parameterAsSource(parameters, lyr.name, context) for lyr in ModelLayer}

        crs = self._get_crs(parameters, context)

        try:
            with logger_to_feedback("gusnet", feedback), logger_to_feedback("wntr", feedback):
                wn = gusnet.from_qgis(sources, flow_unit.name, headloss, project=context.project(), crs=crs)
            check_network(wn)
        except NetworkModelError as e:
            raise QgsProcessingException(tr("Error preparing model: {exception}").format(exception=e)) from None

        wn.options.time.duration = self._get_duration(parameters, context) * 3600
        wn.options.hydraulic.demand_model = self._get_demand_type(parameters, context).value

        return wn

    def _run_simulation(
        self, feedback: QgsProcessingFeedback, wn: wntr.network.WaterNetworkModel
    ) -> wntr.sim.SimulationResults:
        """
        Run the simulation on the given WaterNetworkModel.
        """

        import wntr

        temp_folder = Path(QgsProcessingUtils.tempFolder()) / "wntr"
        sim = wntr.sim.EpanetSimulator(wn)
        try:
            with logger_to_feedback("wntr", feedback):
                sim_results = sim.run_sim(file_prefix=str(temp_folder))
        except wntr.epanet.exceptions.EpanetException as e:
            raise QgsProcessingException(tr("Epanet error: {exception}").format(exception=e)) from None

        return sim_results

    def _describe_model(self, wn: wntr.network.WaterNetworkModel, feedback: QgsProcessingFeedback) -> None:
        if hasattr(feedback, "pushFormattedMessage"):  # QGIS > 3.32
            feedback.pushFormattedMessage(*describe_network(wn))
            feedback.pushFormattedMessage(*describe_pipes(wn))
        else:
            feedback.pushInfo(describe_network(wn)[1])
            feedback.pushInfo(describe_pipes(wn)[1])

    def prepareAlgorithm(  # noqa: N802
        self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback
    ) -> None:
        if QThread.currentThread() == QCoreApplication.instance().thread():
            project_settings = ProjectSettings()
            layers = {
                lyr.name: input_layer.id()
                for lyr in ModelLayer
                if (input_layer := self.parameterAsVectorLayer(parameters, lyr.name, context))
            }
            project_settings.set(SettingKey.MODEL_LAYERS, layers)
            project_settings.set(SettingKey.FLOW_UNITS, self._get_flow_unit(parameters, context))
            project_settings.set(SettingKey.HEADLOSS_FORMULA, self._get_headloss_formula(parameters, context))
            project_settings.set(SettingKey.SIMULATION_DURATION, self._get_duration(parameters, context))
            project_settings.set(SettingKey.DEMAND_TYPE, self._get_demand_type(parameters, context))

        return super().prepareAlgorithm(parameters, context, feedback)

    def write_output_result_layers(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
        wn: wntr.network.WaterNetworkModel,
        sim_results: wntr.sim.SimulationResults,
    ) -> dict[str, str]:
        outputs: dict[str, str] = {}

        with logger_to_feedback("wntr", feedback), logger_to_feedback("gusnet", feedback):
            result_writer = Writer(wn, sim_results)  # type: ignore

        crs = self._get_crs(parameters, context)

        group_name = tr("Simulation Results ({finish_time})").format(finish_time=time.strftime("%X"))
        style_theme = "extended" if wn.options.time.duration > 0 else None
        unit_names = SpecificUnitNames.from_wn(wn)

        for layer_type in ResultLayer:
            fields = result_writer.get_qgsfields(layer_type)

            (sink, layer_id) = self.parameterAsSink(
                parameters, layer_type.results_name, context, fields, layer_type.qgs_wkb_type, crs
            )

            result_writer.write(layer_type, sink)

            outputs[layer_type.results_name] = layer_id

            if not context.willLoadLayerOnCompletion(layer_id):
                continue

            post_processor = LayerPostProcessor(layer_type, style_theme, unit_names)

            layer_details = context.layerToLoadOnCompletionDetails(layer_id)
            layer_details.setPostProcessor(post_processor)
            layer_details.groupName = group_name
            layer_details.layerSortKey = 1 if layer_type is ResultLayer.LINKS else 2

            self.post_processors[layer_id] = post_processor

        return outputs

    def write_inp_file(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
        wn: wntr.network.WaterNetworkModel,
    ) -> dict[str, str]:
        import wntr

        inp_file = self.parameterAsFile(parameters, self.OUTPUT_INP, context)

        wntr.network.write_inpfile(wn, inp_file)

        feedback.pushInfo(tr(".inp file written to: {file_path}").format(file_path=inp_file))

        return {self.OUTPUT_INP: inp_file}


class RunSimulation(_ModelCreatorAlgorithm):
    def createInstance(self):  # noqa N802
        return RunSimulation()

    def name(self):
        return "run"

    def displayName(self):  # noqa N802
        return tr("Run Simulation")

    def shortHelpString(self):  # noqa N802
        return tr("""
This will take all of the model layers (junctions, tanks, reservoirs, pipes, valves, pumps), \
combine them with the chosen options, and run a simulation on WNTR.
The output files are a layer of 'nodes' (junctions, tanks, reservoirs) and \
'links' (pipes, valves, pumps).
Optionally, you can also output an EPANET '.inp' file which can be run / viewed \
in other software.
            """)

    def icon(self):
        return QIcon("gusnet:run.svg")

    def init_output_parameters(self):
        self.init_output_files_parameters()

    @profile(tr("Run Simulation"))
    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict:
        with profile(tr("Verifying Dependencies"), 10, feedback):
            self._check_wntr()

        with profile(tr("Preparing Model"), 30, feedback):
            wn = self._get_wn(parameters, context, feedback)

            self._describe_model(wn, feedback)

        with profile(tr("Running Simulation"), 50, feedback):
            sim_results = self._run_simulation(feedback, wn)

        with profile(tr("Creating Outputs"), 80, feedback):
            outputs = self.write_output_result_layers(parameters, context, feedback, wn, sim_results)

        return outputs


class ExportInpFile(_ModelCreatorAlgorithm):
    def createInstance(self):  # noqa N802
        return ExportInpFile()

    def name(self):
        return "export"

    def displayName(self):  # noqa N802
        return tr("Export Inp File")

    def shortHelpString(self):  # noqa N802
        return tr("""
This will take all of the model layers (junctions, tanks, reservoirs, pipes, valves, pumps), \
combine them with the chosen options, and run a simulation on WNTR.
The output files are a layer of 'nodes' (junctions, tanks, reservoirs) and \
'links' (pipes, valves, pumps).
Optionally, you can also output an EPANET '.inp' file which can be run / viewed \
in other software.
            """)

    def icon(self):
        return QgsApplication.getThemeIcon("mActionFileSave.svg")

    def init_output_parameters(self):
        self.init_export_inp_parameter()

    @profile(tr("Export Inp File"))
    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict:
        with profile(tr("Verifying Dependencies"), 10, feedback):
            self._check_wntr()

        with profile(tr("Preparing Model"), 30, feedback):
            wn = self._get_wn(parameters, context, feedback)

            self._describe_model(wn, feedback)

        with profile(tr("Creating Outputs"), 80, feedback):
            outputs = self.write_inp_file(parameters, context, feedback, wn)

        return outputs


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    def __init__(self, layer_type: ResultLayer, style_theme: str | None, unit_names: SpecificUnitNames):
        super().__init__()
        self.layer_type = layer_type
        self.style_theme = style_theme
        self.unit_names = unit_names

    def postProcessLayer(self, layer, context, feedback):  # noqa N802 ARG002
        style(layer, self.layer_type, self.style_theme, self.unit_names)


@contextmanager
def logger_to_feedback(logger_name: str, feedback: QgsProcessingFeedback):
    """
    Context manager to redirect logging messages to QgsProcessingFeedback.
    """

    class FeedbackHandler(logging.Handler):
        def emit(self, record):
            feedback.pushWarning(record.getMessage())

    logger = logging.getLogger(logger_name)
    logger.propagate = False
    logging_handler = FeedbackHandler()
    logging_handler.setLevel("INFO")
    logger.addHandler(logging_handler)

    try:
        yield
    finally:
        logger.propagate = True
        logger.removeHandler(logging_handler)
