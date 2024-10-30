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
from typing import Any, ClassVar  # noqa F401

from qgis.core import (
    QgsFields,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterMatrix,
    QgsProcessingParameterVectorLayer,
    QgsProcessingUtils,
    QgsProject,
)

import wntrqgis.options
from wntrqgis.utilswithoutwntr import WqFlowUnit, WqInField, WqInLayer, WqOutLayer, WqProjectVar, WqUtil
from wntrqgis.wntrqgis_processing.common import LayerPostProcessor, ProgStatus, WntrQgisProcessingBase


class RunSimulation(QgsProcessingAlgorithm, WntrQgisProcessingBase):
    OPTIONSHYDRAULIC = "OPTIONSHYDRAULIC"
    OPTIONSTIME = "OPTIONSTIME"

    CONTROLS = "CONTROLS"
    UNITS = "UNITS"
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
        default_layers = WqUtil.get_project_var(WqProjectVar.INLAYERS)
        if not isinstance(default_layers, dict):
            default_layers = {}

        for lyr in WqInLayer:
            param = QgsProcessingParameterVectorLayer(
                lyr.name,
                self.tr(lyr.friendly_name),
                types=lyr.acceptable_processing_vectors,
                optional=lyr is not WqInLayer.JUNCTIONS,
            )
            savedlyr = default_layers.get(lyr.name)
            if savedlyr and param.checkValueIsAcceptable(savedlyr) and QgsProject.instance().mapLayer(savedlyr):
                param.setGuiDefaultValueOverride(savedlyr)
            param.setHelp(self.tr("Model Inputs"))
            self.addParameter(param)

        default_flow_units = WqUtil.get_project_var(WqProjectVar.FLOW_UNITS)

        self.addParameter(
            QgsProcessingParameterEnum(
                self.UNITS,
                self.tr("Units"),
                options=list(WqFlowUnit),
                allowMultiple=False,
                usesStaticStrings=False,
                defaultValue=(
                    WqFlowUnit[default_flow_units].value if default_flow_units in WqFlowUnit.__members__ else None
                ),
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(WqOutLayer.NODES.value, self.tr("Simulation Results - Nodes"))
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(WqOutLayer.LINKS.value, self.tr("Simulation Results - Links"))
        )

        saved_options = WqUtil.get_project_var(WqProjectVar.OPTIONS)

        default_options = wntrqgis.options.get_default_options()

        optionslist = {}

        for optionskey in ["time", "hydraulic"]:
            if isinstance(default_options[optionskey], dict):
                if isinstance(saved_options, dict):
                    optionsdict = default_options[optionskey] | saved_options.get(optionskey, {})
                else:
                    optionsdict = default_options[optionskey]

                optionslist[optionskey] = []
                for x, y in optionsdict.items():
                    optionslist[optionskey].append(x)
                    optionslist[optionskey].append(y)

        param = QgsProcessingParameterMatrix(
            self.OPTIONSTIME,
            "Time Settings",
            numberRows=1,
            hasFixedNumberRows=True,
            headers=["Setting Name", "Setting Value"],
            defaultValue=optionslist["time"],
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        param = QgsProcessingParameterMatrix(
            self.OPTIONSHYDRAULIC,
            "Hydraulic Settings",
            numberRows=1,
            hasFixedNumberRows=True,
            headers=["Setting Name", "Setting Value"],
            defaultValue=optionslist["hydraulic"],
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        param = QgsProcessingParameterFileDestination(
            self.OUTPUTINP, "Output .inp file", optional=True, createByDefault=False
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        # param = QgsProcessingParameterString(self.CONTROLS, "Controls", multiLine=True)
        # param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        # param.setGuiDefaultValueOverride()
        # self.addParameter(param)

    def processAlgorithm(self, parameters, context, feedback):  # noqa N802
        if feedback is None:
            feedback = QgsProcessingFeedback()

        # PREPARE IMPORTS
        # imports are here as they are slow and only needed when processing the model.
        self._check_and_unpack_dependencies(feedback)

        try:
            import geopandas as gpd
            import pandas as pd  # if geopadas installed this should not pose a problem!
            import shapely
            import wntr

            from wntrqgis.utilswithwntr import WqWntrUtils
        except ImportError as e:
            raise QgsProcessingException(e) from e

        feedback.pushDebugInfo("WNTR version: " + wntr.__version__)

        if feedback.isCanceled():
            return {}
        self._update_progress(feedback, ProgStatus.PREPARING_MODEL)

        flow_unit_string = self.parameterAsEnum(parameters, self.UNITS, context)
        if flow_unit_string is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.UNITS))
        flow_units = wntr.epanet.util.FlowUnits[list(WqFlowUnit)[flow_unit_string].name]

        options_hydraulic = self.parameterAsMatrix(parameters, self.OPTIONSHYDRAULIC, context)
        options_time = self.parameterAsMatrix(parameters, self.OPTIONSTIME, context)

        # START WNTR MODEL
        # creation order to be options, patterns/cruves, nodes, then links
        wn = wntr.network.WaterNetworkModel()

        # ADD OPTIONS

        options_hydraulic_dict = {}
        for i in range(0, len(options_hydraulic), 2):
            options_hydraulic_dict[options_hydraulic[i]] = options_hydraulic[i + 1]
        wn.options.hydraulic = wntr.network.options.HydraulicOptions(**options_hydraulic_dict)

        options_time_dict = {}
        for i in range(0, len(options_time), 2):
            options_time_dict[options_time[i]] = options_time[i + 1]
        wn.options.time = wntr.network.options.TimeOptions(**options_time_dict)

        gdf_inputs = {}
        for in_layer in WqInLayer:
            lyr = self.parameterAsVectorLayer(parameters, in_layer.name, context)
            if lyr is None:
                continue
            crs = lyr.crs()
            gdf = gpd.GeoDataFrame.from_features(lyr.getFeatures())

            gdf.dropna(how="all", axis=1, inplace=True)
            if gdf.empty:
                continue

            # to fix bug in wntr 1.2.0, where 'node_type' and 'link_type' are required
            gdf["node_type" if in_layer.is_node else "link_type"] = in_layer.node_link_type

            # this is for shapefiles, but must not apply otherwise or causes problems
            if not in_layer.is_node and isinstance(gdf["geometry"].iloc[0], shapely.MultiLineString):
                gdf["geometry"] = gdf["geometry"].apply(lambda g: g.geoms[0])  # shapefiles are multi line strings

            # below line should only affect shapefiles
            shape_name_map = {wq_field.value[:10]: wq_field.value for wq_field in WqInField}
            gdf.rename(columns=shape_name_map, inplace=True, errors="ignore")

            gdf.set_index("name", inplace=True)
            gdf.index.rename(None, inplace=True)

            gdf_inputs[in_layer] = gdf

        # unit conversion
        WqWntrUtils.convert_dfs_to_si(gdf_inputs, flow_units, wn.options.hydraulic.headloss == "D-W")

        # PREPARE PATTERNS AND CURVES
        WqWntrUtils.patterns_curves_from_df(gdf_inputs, wn, flow_units)

        if feedback.isCanceled():
            return {}

        wn.from_gis({lyr.wntr_attr: df for lyr, df in gdf_inputs.items()})

        # ADD DEMANDS - wntr 1.2 doesn't handle this automatically
        if WqInLayer.JUNCTIONS in gdf_inputs:
            WqWntrUtils.add_demands_to_wntr(gdf_inputs[WqInLayer.JUNCTIONS], wn)

        if feedback.isCanceled():
            return {}
        self._describe_model(feedback, wn)

        # RUN SIMULATION
        self._update_progress(feedback, ProgStatus.RUNNING_SIMULATION)

        # create logger
        logger = logging.getLogger("wntr")
        ch = LoggingHandler(feedback)
        ch.setLevel(logging.WARNING)
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        outputs = {}

        tempfolder = QgsProcessingUtils.tempFolder() + "/wntr"
        inpfile = self.parameterAsFile(parameters, self.OUTPUTINP, context)
        if inpfile:
            wntr.network.write_inpfile(wn, inpfile)
            outputs = {self.OUTPUTINP: inpfile}
        try:
            sim = wntr.sim.EpanetSimulator(wn)
            results = sim.run_sim(file_prefix=tempfolder)  # by default, this runs EPANET 2.2.0
        except Exception as e:
            if inpfile:
                feedback.pushInfo(".inp file written to: " + inpfile)  # only push this message on failure
            raise QgsProcessingException("Error running model: " + str(e)) from e

        if feedback.isCanceled():
            return {}
        self._update_progress(feedback, ProgStatus.SIMULATION_COMPLETED)

        # PROCESS SIMULATION RESULTS

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
                crs,
            )

            in_items = pd.concat([gdf.geometry for inlyr, gdf in gdf_inputs.items() if inlyr.is_node == lyr.is_node])
            result_gdfs = getattr(results, lyr.wntr_attr)

            WqWntrUtils.result_gdfs_to_sink(result_gdfs, lyr.wq_fields, in_items, sink)

        self._update_progress(feedback, ProgStatus.FINISHED_PROCESSING)

        # PREPARE TO LOAD LAYER STYLES IN MAIN THREAD ONCE FINISHED

        for outputname, lyr_id in outputs.items():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(outputname)
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])

        return outputs


class LoggingHandler(logging.StreamHandler):
    def __init__(self, feedback):
        logging.StreamHandler.__init__(self)
        self.feedback = feedback

    def emit(self, record):
        msg = self.format(record)
        self.feedback.pushWarning(msg)
