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

from wntrqgis.utilswithoutwntr import WqFlowUnit, WqHeadlossFormula, WqInField, WqModelLayer, WqOutLayer, WqProjectVar
from wntrqgis.wntrqgis_processing.common import LayerPostProcessor, ProgStatus, WntrQgisProcessingBase


class RunSimulation(QgsProcessingAlgorithm, WntrQgisProcessingBase):
    OPTIONSHYDRAULIC = "OPTIONSHYDRAULIC"
    OPTIONSTIME = "OPTIONSTIME"

    CONTROLS = "CONTROLS"
    UNITS = "UNITS"
    DURATION = "DURATION"
    HEADLOSS_FORMULA = "HEADLOSS_FORMULA"
    OUTPUTINP = "OUTPUTINP"

    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.Flag.FlagRequiresMatchingCrs

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

    def initAlgorithm(self, config=None):  # noqa N802
        # default_layers = QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable("wntr_layers")
        default_layers = WqProjectVar.INLAYERS.get()
        if not isinstance(default_layers, dict):
            default_layers = {}

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
            param.setHelp(self.tr("Model Inputs"))
            self.addParameter(param)

        param = QgsProcessingParameterEnum(
            self.UNITS,
            self.tr("Units"),
            options=list(WqFlowUnit),
            allowMultiple=False,
            usesStaticStrings=False,
        )
        default_flow_units = WqProjectVar.FLOW_UNITS.get()
        param.setGuiDefaultValueOverride(list(WqFlowUnit).index(default_flow_units) if default_flow_units else None)
        self.addParameter(param)

        param = QgsProcessingParameterEnum(
            self.HEADLOSS_FORMULA,
            self.tr("Headloss Formula"),
            options=[formula.friendly_name() for formula in WqHeadlossFormula],
            allowMultiple=False,
            usesStaticStrings=False,
        )
        default_hl_formula = WqProjectVar.HEADLOSS_FORMULA.get()
        param.setGuiDefaultValueOverride(
            list(WqHeadlossFormula).index(default_hl_formula) if default_hl_formula else None
        )
        self.addParameter(param)

        param = QgsProcessingParameterNumber(
            self.DURATION, self.tr("Simulation duration in hours (or 0 for single period)"), minValue=0
        )
        param.setGuiDefaultValueOverride(WqProjectVar.SIMULATION_DURATION.get())
        self.addParameter(param)

        self.addParameter(
            QgsProcessingParameterFeatureSink(WqOutLayer.NODES.value, self.tr("Simulation Results - Nodes"))
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(WqOutLayer.LINKS.value, self.tr("Simulation Results - Links"))
        )

        # saved_options = WqProjectVar.OPTIONS.get()

        # default_options = wntrqgis.options.get_default_options()

        # optionslist = {}

        # for optionskey in ["time", "hydraulic"]:
        #     if isinstance(default_options[optionskey], dict):
        #         if isinstance(saved_options, dict):
        #             optionsdict = default_options[optionskey] | saved_options.get(optionskey, {})
        #         else:
        #             optionsdict = default_options[optionskey]

        #         optionslist[optionskey] = []
        #         for x, y in optionsdict.items():
        #             optionslist[optionskey].append(x)
        #             optionslist[optionskey].append(y)

        # param = QgsProcessingParameterMatrix(
        #     self.OPTIONSTIME,
        #     "Time Settings",
        #     numberRows=1,
        #     hasFixedNumberRows=True,
        #     headers=["Setting Name", "Setting Value"],
        #     defaultValue=optionslist["time"],
        # )
        # param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        # self.addParameter(param)

        # param = QgsProcessingParameterMatrix(
        #     self.OPTIONSHYDRAULIC,
        #     "Hydraulic Settings",
        #     numberRows=1,
        #     hasFixedNumberRows=True,
        #     headers=["Setting Name", "Setting Value"],
        #     defaultValue=optionslist["hydraulic"],
        # )
        # param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        # self.addParameter(param)

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

        # PREPARE IMPORTS
        # imports are here as they are slow and only needed when processing the model.
        self._check_and_unpack_dependencies()

        try:
            import wntr

            from wntrqgis.utilswithwntr import (
                WqNetworkModel,
                WqNetworkModelError,
                WqSimulationResults,
                WqUnitConversion,
            )
        except ImportError as e:
            raise QgsProcessingException(e) from e

        feedback.pushDebugInfo("WNTR version: " + wntr.__version__)

        if feedback.isCanceled():
            return {}
        self._update_progress(ProgStatus.PREPARING_MODEL)

        # create logger
        logger = logging.getLogger("wntr")
        ch = LoggingHandler(feedback)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # START WNTR MODEL
        # creation order to be options, patterns/cruves, nodes, then links
        wn = wntr.network.WaterNetworkModel()

        # ADD OPTIONS

        flow_unit_num = self.parameterAsEnum(parameters, self.UNITS, context)
        if parameters[self.UNITS] is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.UNITS))
        wq_flow_unit = list(WqFlowUnit)[flow_unit_num]
        WqProjectVar.FLOW_UNITS.set(wq_flow_unit)

        input_headloss_formula = list(WqHeadlossFormula)[
            self.parameterAsEnum(parameters, self.HEADLOSS_FORMULA, context)
        ]
        wn.options.hydraulic.headloss = input_headloss_formula.value

        unit_conversion = WqUnitConversion(wq_flow_unit, input_headloss_formula)

        duration = self.parameterAsDouble(parameters, self.DURATION, context)
        wn.options.time.duration = duration * 3600

        sources = {lyr: self.parameterAsSource(parameters, lyr.name, context) for lyr in WqModelLayer}
        network_model = WqNetworkModel(unit_conversion, context.transformContext(), context.ellipsoid())
        try:
            wn = network_model.to_wntr(sources, wn)
        except WqNetworkModelError as e:
            raise QgsProcessingException(self.tr("Error preparing model - " + str(e))) from None

        if feedback.isCanceled():
            return {}
        self._describe_model(wn)
        self._update_progress(ProgStatus.RUNNING_SIMULATION)

        outputs = {}

        tempfolder = QgsProcessingUtils.tempFolder() + "/wntr"
        inpfile = self.parameterAsFile(parameters, self.OUTPUTINP, context)
        if inpfile:
            wntr.network.write_inpfile(wn, inpfile)
            outputs = {self.OUTPUTINP: inpfile}

        sim = wntr.sim.EpanetSimulator(wn)
        try:
            sim_results = sim.run_sim(file_prefix=tempfolder)  # by default, this runs EPANET 2.2.0
        except wntr.epanet.exceptions.EpanetException as e:
            if inpfile:
                feedback.pushInfo(".inp file written to: " + inpfile)  # only push this message on failure
            raise QgsProcessingException("Epanet error: " + str(e)) from None

        if feedback.isCanceled():
            return {}
        self._update_progress(ProgStatus.CREATING_OUTPUTS)

        # PROCESS SIMULATION RESULTS
        wq_results = WqSimulationResults(sim_results, unit_conversion)
        # wq_results.darcy_weisbach = wn.options.hydraulic.headloss == "D-W"
        # wq_results.flow_units = flow_units

        for lyr in WqOutLayer:
            fields = QgsFields()
            fields.append(WqInField.NAME.qgs_field)
            for f in lyr.wq_fields:
                fields.append(f.qgs_field)

            (sink, outputs[lyr.value]) = self.parameterAsSink(
                parameters,
                lyr.value,
                context,
                fields,
                lyr.qgs_wkb_type,
                network_model.crs,
            )

            wq_results.to_sink(sink, lyr.wq_fields, network_model.geom_dict[lyr])

        logger.removeHandler(ch)
        self._update_progress(ProgStatus.FINISHED_PROCESSING)
        WqProjectVar.HEADLOSS_FORMULA.set(WqHeadlossFormula(wn.options.hydraulic.headloss))
        WqProjectVar.SIMULATION_DURATION.set(wn.options.time.duration)
        # PREPARE TO LOAD LAYER STYLES IN MAIN THREAD ONCE FINISHED
        finishtime = time.strftime("%X")
        for outputname, lyr_id in outputs.items():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(
                    outputname, self.tr(f"Simulation Results ({finishtime})")
                )
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])

        return outputs


class LoggingHandler(logging.StreamHandler):
    def __init__(self, feedback):
        logging.StreamHandler.__init__(self)
        self.feedback = feedback

    def emit(self, record):
        msg = self.format(record)
        self.feedback.pushWarning(msg)
