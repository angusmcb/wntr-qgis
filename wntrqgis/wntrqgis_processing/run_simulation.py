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
from typing import Any, ClassVar  # noqa F401

from qgis.core import (
    QgsProcessingAlgorithm,
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
from wntrqgis.wntrqgis_processing.common import Progression, WntrQgisProcessingBase


class RunSimulation(QgsProcessingAlgorithm, WntrQgisProcessingBase):
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

    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict:
        WntrQgisProcessingBase.processAlgorithm(self, parameters, context, feedback)

        self._ensure_wntr()
        # only import wntr-using modules once we are sure wntr is installed.
        import wntr

        self._update_progress(Progression.PREPARING_MODEL)

        class FeedbackHandler(logging.Handler):
            def emit(self, record):
                feedback.pushWarning(record.getMessage())

        logger = logging.getLogger("wntr")
        logger.propagate = False
        logging_handler = FeedbackHandler()
        logging_handler.setLevel("INFO")
        logger.addHandler(logging_handler)

        project_settings = ProjectSettings(context.project())

        # start wntr model
        # add to model order to be: options, patterns/cruves, nodes, then links
        wn = wntr.network.WaterNetworkModel()

        flow_unit_index = self.parameterAsEnum(parameters, self.UNITS, context)
        wq_flow_unit = list(FlowUnit)[flow_unit_index]
        project_settings.set(SettingKey.FLOW_UNITS, wq_flow_unit)
        wn.options.hydraulic.inpfile_units = wq_flow_unit.name

        headloss_formula_index = self.parameterAsEnum(parameters, self.HEADLOSS_FORMULA, context)
        headloss_formula = list(HeadlossFormula)[headloss_formula_index]
        project_settings.set(SettingKey.HEADLOSS_FORMULA, headloss_formula)
        wn.options.hydraulic.headloss = headloss_formula.value

        duration = self.parameterAsDouble(parameters, self.DURATION, context)
        project_settings.set(SettingKey.SIMULATION_DURATION, duration)
        wn.options.time.duration = duration * 3600

        sources = {lyr.name: self.parameterAsSource(parameters, lyr.name, context) for lyr in ModelLayer}

        layers_for_settings = {
            lyr.name: input_layer.id()
            for lyr in ModelLayer
            if (input_layer := self.parameterAsVectorLayer(parameters, lyr.name, context))
        }
        project_settings.set(SettingKey.MODEL_LAYERS, layers_for_settings)

        try:
            crs = sources[ModelLayer.JUNCTIONS.name].sourceCrs()
        except AttributeError:
            raise QgsProcessingException(tr("A junctions layer is required.")) from None

        try:
            # network_model.add_features_to_network_model(sources, wn)
            wntrqgis.from_qgis(sources, wq_flow_unit.name, wn=wn, project=context.project(), crs=crs)
            check_network(wn)
        except NetworkModelError as e:
            raise QgsProcessingException(tr("Error preparing model: {exception}").format(exception=e)) from None

        self._describe_model(wn)

        outputs: dict[str, str] = {}

        inp_file = self.parameterAsFile(parameters, self.OUTPUTINP, context)
        if inp_file:
            wntr.network.write_inpfile(wn, inp_file)
            outputs[self.OUTPUTINP] = inp_file
            feedback.pushInfo(".inp file written to: " + inp_file)

        self._update_progress(Progression.RUNNING_SIMULATION)

        temp_folder = QgsProcessingUtils.tempFolder() + "/wntr"
        sim = wntr.sim.EpanetSimulator(wn)
        try:
            sim_results = sim.run_sim(file_prefix=temp_folder)
        except wntr.epanet.exceptions.EpanetException as e:
            raise QgsProcessingException(tr("Epanet error: {exception}").format(exception=e)) from None

        self._update_progress(Progression.CREATING_OUTPUTS)

        result_writer = Writer(wn, sim_results, units=wq_flow_unit.name)

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

        logger.removeHandler(logging_handler)
        self._update_progress(Progression.FINISHED_PROCESSING)

        finish_time = time.strftime("%X")
        style_theme = "extended" if wn.options.time.duration > 0 else None
        self._setup_postprocessing(
            layers, tr("Simulation Results ({finish_time})").format(finish_time=finish_time), False, style_theme, True
        )

        return outputs
