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
from typing import Any, ClassVar  # noqa F401

from qgis.core import (
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
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

import wntrqgis
from wntrqgis.elements import (
    FlowUnit,
    HeadlossFormula,
    ModelLayer,
    ResultLayer,
)
from wntrqgis.i18n import tr
from wntrqgis.interface import (
    NetworkModelError,
    Writer,
    check_network,
)
from wntrqgis.settings import ProjectSettings, SettingKey
from wntrqgis.wntrqgis_processing.common import Progression, ProgressTracker, WntrQgisProcessingBase


class RunSimulation(WntrQgisProcessingBase):
    UNITS = "UNITS"
    DURATION = "DURATION"
    HEADLOSS_FORMULA = "HEADLOSS_FORMULA"
    OUTPUTINP = "OUTPUTINP"

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
        return QIcon(":/wntrqgis/run.svg")

    def initAlgorithm(self, config=None):  # noqa N802
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

        self.addParameter(
            QgsProcessingParameterFeatureSink(ResultLayer.NODES.results_name, tr("Simulation Results - Nodes"))
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(ResultLayer.LINKS.results_name, tr("Simulation Results - Links"))
        )

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUTINP, tr("Output .inp file"), optional=True, createByDefault=False
            )
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

    def _get_duration(self, parameters: dict[str, Any], context: QgsProcessingContext) -> float:
        """
        Get the simulation duration from the parameters.
        """
        duration = self.parameterAsDouble(parameters, self.DURATION, context)
        if duration < 0:
            raise QgsProcessingException(tr("Simulation duration must be greater than or equal to 0."))
        return duration

    def prepareAlgorithm(self, parameters, context, feedback):  # noqa: N802
        if QThread.currentThread() == QCoreApplication.instance().thread() and hasattr(self, "_settings"):
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

        return super().prepareAlgorithm(parameters, context, feedback)

    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict:
        progress = ProgressTracker(feedback)

        self._ensure_wntr(progress)
        # only import wntr-using modules once we are sure wntr is installed.
        import wntr

        progress.update_progress(Progression.PREPARING_MODEL)

        with logger_to_feedback("wntr", feedback):
            # add to model order to be: options, patterns/cruves, nodes, then links
            wn = wntr.network.WaterNetworkModel()

            flow_unit = self._get_flow_unit(parameters, context)
            wn.options.hydraulic.inpfile_units = flow_unit.name

            wn.options.hydraulic.headloss = self._get_headloss_formula(parameters, context).value

            wn.options.time.duration = self._get_duration(parameters, context) * 3600

            sources = {lyr.name: self.parameterAsSource(parameters, lyr.name, context) for lyr in ModelLayer}

            try:
                crs = sources[ModelLayer.JUNCTIONS.name].sourceCrs()
            except AttributeError:
                raise QgsProcessingException(tr("A junctions layer is required.")) from None

            try:
                wntrqgis.from_qgis(sources, flow_unit.name, wn=wn, project=context.project(), crs=crs)
                check_network(wn)
            except NetworkModelError as e:
                raise QgsProcessingException(tr("Error preparing model: {exception}").format(exception=e)) from None

            self._describe_model(wn, feedback)

            outputs: dict[str, str] = {}

            inp_file = self.parameterAsFile(parameters, self.OUTPUTINP, context)
            if inp_file:
                wntr.network.write_inpfile(wn, inp_file)
                outputs[self.OUTPUTINP] = inp_file
                feedback.pushInfo(".inp file written to: " + inp_file)

            progress.update_progress(Progression.RUNNING_SIMULATION)

            temp_folder = Path(QgsProcessingUtils.tempFolder()) / "wntr"
            sim = wntr.sim.EpanetSimulator(wn)
            try:
                sim_results = sim.run_sim(file_prefix=str(temp_folder))
            except wntr.epanet.exceptions.EpanetException as e:
                raise QgsProcessingException(tr("Epanet error: {exception}").format(exception=e)) from None

            progress.update_progress(Progression.CREATING_OUTPUTS)

            result_writer = Writer(wn, sim_results, units=flow_unit.name)

            layers = {}

            for lyr in ResultLayer:
                (sink, outputs[lyr.results_name]) = self.parameterAsSink(
                    parameters,
                    lyr.results_name,
                    context,
                    result_writer.get_qgsfields(lyr),
                    lyr.qgs_wkb_type,
                    crs,
                )
                layers[lyr] = outputs[lyr.results_name]
                result_writer.write(lyr, sink)

        progress.update_progress(Progression.FINISHED_PROCESSING)

        finish_time = time.strftime("%X")
        style_theme = "extended" if wn.options.time.duration > 0 else None
        self._setup_postprocessing(
            context,
            layers,
            tr("Simulation Results ({finish_time})").format(finish_time=finish_time),
            False,
            style_theme,
            True,
        )

        return outputs


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
