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
    QgsFields,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsProcessingUtils,
    QgsProject,
)

from wntrqgis.network_parts import (
    WqFlowUnit,
    WqHeadlossFormula,
    WqModelField,
    WqModelLayer,
    WqProjectSetting,
    WqProjectSettings,
    WqResultLayer,
)
from wntrqgis.resource_manager import WqIcon
from wntrqgis.wntrqgis_processing.common import ProgStatus, WntrQgisProcessingBase


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
        return self.tr("Run Simulation")

    def shortHelpString(self):  # noqa N802
        return self.tr("""
            This will take all of the model layers (junctions, tanks, reservoirs, pipes, valves, pumps), \
            combine them with the chosen options, and run a simulation on WNTR.
            The output files are a layer of 'nodes' (junctions, tanks, reservoirs) and \
            'links' (pipes, valves, pumps).
            Optionally, you can also output an EPANET '.inp' file which can be run / viewed \
            in other software.
            """)

    def icon(self):
        return WqIcon.RUN.q_icon

    def initAlgorithm(self, config=None):  # noqa N802
        project_settings = WqProjectSettings(QgsProject.instance())

        default_layers = project_settings.get(WqProjectSetting.MODEL_LAYERS, {})
        for lyr in WqModelLayer:
            param = QgsProcessingParameterFeatureSource(
                lyr.name,
                self.tr(lyr.friendly_name),
                types=lyr.acceptable_processing_vectors,
                optional=lyr is not WqModelLayer.JUNCTIONS,
            )
            savedlyr = default_layers.get(lyr.name)
            if savedlyr and param.checkValueIsAcceptable(savedlyr) and QgsProject.instance().mapLayer(savedlyr):
                param.setGuiDefaultValueOverride(savedlyr)

            self.addParameter(param)

        param = QgsProcessingParameterEnum(
            self.UNITS,
            self.tr("Units"),
            options=[fu.value for fu in WqFlowUnit],
            allowMultiple=False,
            usesStaticStrings=False,
        )
        default_flow_units = project_settings.get(WqProjectSetting.FLOW_UNITS)
        param.setGuiDefaultValueOverride(list(WqFlowUnit).index(default_flow_units) if default_flow_units else None)
        self.addParameter(param)

        param = QgsProcessingParameterEnum(
            self.HEADLOSS_FORMULA,
            self.tr("Headloss Formula"),
            options=[formula.friendly_name for formula in WqHeadlossFormula],
            allowMultiple=False,
            usesStaticStrings=False,
        )
        default_hl_formula = project_settings.get(WqProjectSetting.HEADLOSS_FORMULA)
        param.setGuiDefaultValueOverride(
            list(WqHeadlossFormula).index(default_hl_formula) if default_hl_formula else None
        )
        self.addParameter(param)

        param = QgsProcessingParameterNumber(
            self.DURATION, self.tr("Simulation duration in hours (or 0 for single period)"), minValue=0
        )
        param.setGuiDefaultValueOverride(project_settings.get(WqProjectSetting.SIMULATION_DURATION, 0))
        self.addParameter(param)

        self.addParameter(
            QgsProcessingParameterFeatureSink(WqResultLayer.NODES.value, self.tr("Simulation Results - Nodes"))
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(WqResultLayer.LINKS.value, self.tr("Simulation Results - Links"))
        )

        param = QgsProcessingParameterFileDestination(
            self.OUTPUTINP, "Output .inp file", optional=True, createByDefault=False
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

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

        from wntrqgis.wntr_interface import (
            WqNetworkModelError,
            WqNetworkToWntr,
            WqSimulationResults,
            WqUnitConversion,
        )

        self._update_progress(ProgStatus.PREPARING_MODEL)

        # create logger
        logger = logging.getLogger("wntr")
        wntr_logger_handler = LoggingHandler(feedback, logging.INFO, "%(levelname)s - %(message)s")
        logger.addHandler(wntr_logger_handler)

        project_settings = WqProjectSettings(context.project())

        # start wntr model
        # add to model order to be: options, patterns/cruves, nodes, then links
        wn = wntr.network.WaterNetworkModel()

        flow_unit_index = self.parameterAsEnum(parameters, self.UNITS, context)
        wq_flow_unit = list(WqFlowUnit)[flow_unit_index]
        project_settings.set(WqProjectSetting.FLOW_UNITS, wq_flow_unit)

        headloss_formula_index = self.parameterAsEnum(parameters, self.HEADLOSS_FORMULA, context)
        headloss_formula = list(WqHeadlossFormula)[headloss_formula_index]
        project_settings.set(WqProjectSetting.HEADLOSS_FORMULA, headloss_formula)
        wn.options.hydraulic.headloss = headloss_formula.value

        duration = self.parameterAsDouble(parameters, self.DURATION, context)
        project_settings.set(WqProjectSetting.SIMULATION_DURATION, duration)
        wn.options.time.duration = duration * 3600

        sources = {lyr: self.parameterAsSource(parameters, lyr.name, context) for lyr in WqModelLayer}

        unit_conversion = WqUnitConversion(wq_flow_unit, headloss_formula)

        network_model = WqNetworkToWntr(unit_conversion, context.transformContext(), context.ellipsoid())
        try:
            wn = network_model.to_wntr(sources, wn)
        except WqNetworkModelError as e:
            raise QgsProcessingException(self.tr("Error preparing model - " + str(e))) from None

        self._describe_model(wn)

        outputs: dict[str, str] = {}

        inpfile = self.parameterAsFile(parameters, self.OUTPUTINP, context)
        if inpfile:
            wntr.network.write_inpfile(wn, inpfile)
            outputs[self.OUTPUTINP] = inpfile
            feedback.pushInfo(".inp file written to: " + inpfile)

        self._update_progress(ProgStatus.RUNNING_SIMULATION)

        tempfolder = QgsProcessingUtils.tempFolder() + "/wntr"
        sim = wntr.sim.EpanetSimulator(wn)
        try:
            sim_results = sim.run_sim(file_prefix=tempfolder)  # by default, this runs EPANET 2.2.0
        except wntr.epanet.exceptions.EpanetException as e:
            raise QgsProcessingException("Epanet error: " + str(e)) from None

        self._update_progress(ProgStatus.CREATING_OUTPUTS)

        # PROCESS SIMULATION RESULTS
        wq_results = WqSimulationResults(sim_results, unit_conversion)

        for lyr in WqResultLayer:
            fields = QgsFields()
            fields.append(WqModelField.NAME.qgs_field)
            for f in lyr.wq_fields:
                fields.append(f.qgs_field)

            (sink, outputs[lyr]) = self.parameterAsSink(
                parameters,
                lyr.value,
                context,
                fields,
                lyr.qgs_wkb_type,
                network_model.crs,
            )

            wq_results.to_sink(sink, lyr.wq_fields, network_model.geom_dict[lyr.element_family])

        logger.removeHandler(wntr_logger_handler)
        self._update_progress(ProgStatus.FINISHED_PROCESSING)

        finishtime = time.strftime("%X")

        self._setup_postprocessing(outputs, f"Simulation Results ({finishtime})", False)

        return outputs


class LoggingHandler(logging.StreamHandler):
    def __init__(self, feedback, logging_level, format_string):
        logging.StreamHandler.__init__(self)
        self.feedback = feedback
        self.setLevel(logging_level)
        self.setFormatter(logging.Formatter(format_string))

    def emit(self, record):
        msg = self.format(record)
        self.feedback.pushWarning(msg)
