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

import ast
import logging
import os
import sys
from typing import Any, ClassVar  # noqa F401

from qgis.core import (
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterMatrix,
    QgsProcessingParameterVectorLayer,
    QgsProcessingUtils,
    QgsProject,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication, QMetaType, QVariant

import wntrqgis.options
from wntrqgis import environment_tools
from wntrqgis.wntrqgis_processing.LayerPostProcessor import LayerPostProcessor


class RunSimulation(QgsProcessingAlgorithm):
    OPTIONSHYDRAULIC = "OPTIONSHYDRAULIC"
    OPTIONSTIME = "OPTIONSTIME"

    JUNCTIONS = "JUNCTIONS"
    TANKS = "TANKS"
    RESERVOIRS = "RESERVOIRS"
    PIPES = "PIPES"
    PUMPS = "PUMPS"
    VALVES = "VALVES"

    OUTPUTNODES = "OUTPUTNODES"
    OUTPUTLINKS = "OUTPUTLINKS"
    post_processors: ClassVar[dict[str, LayerPostProcessor]] = {}
    wn = None
    name_increment = 0

    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.Flag.FlagRequiresMatchingCrs

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):  # noqa N802
        return RunSimulation()

    def name(self):
        return "run"

    def displayName(self):  # noqa N802
        return self.tr("Run Simulation")

    def shortHelpString(self):  # noqa N802
        return self.tr("Example algorithm short description")

    def initAlgorithm(self, config=None):  # noqa N802
        default_layers = QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable("wntr_layers")
        if not isinstance(default_layers, dict):
            default_layers = {}

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.JUNCTIONS,
                "Junctions",
                types=[QgsProcessing.TypeVectorPoint],
                defaultValue=default_layers.get("JUNCTIONS"),
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.TANKS,
                "Tanks",
                types=[QgsProcessing.TypeVectorPoint],
                defaultValue=default_layers.get("TANKS"),
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.RESERVOIRS,
                "Reservoirs",
                types=[QgsProcessing.TypeVectorPoint],
                defaultValue=default_layers.get("RESERVOIRS"),
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.PIPES,
                "Pipes",
                types=[QgsProcessing.TypeVectorLine],
                defaultValue=default_layers.get("PIPES"),
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.PUMPS, "Pumps", defaultValue=default_layers.get("PUMPS"), optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.VALVES, "Valves", defaultValue=default_layers.get("VALVES"), optional=True
            )
        )

        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUTNODES, self.tr("Simulation Results - Nodes")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUTLINKS, self.tr("Simulation Results - Links")))

        options = QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable("wntr_options")

        optionslist = wntrqgis.options.default_options
        if options:
            for i in options:
                optionslist[i] = []
                for x, y in options[i].items():
                    optionslist[i].append(x)
                    optionslist[i].append(y)

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

    def processAlgorithm(self, parameters, context, feedback):  # noqa N802
        # PREPARE IMPORTS
        # imports are here as they are slow and only needed when processing the model.
        feedback.setProgressText("Checking dependencies")

        if environment_tools.check_dependencies():
            msg = "Missing Dependencies"
            raise QgsProcessingException(msg)
        try:
            import geopandas as gpd
        except ImportError as e:
            msg = "Geopandas is not installed"
            raise QgsProcessingException(msg) from e
        import pandas as pd  # if geopadas installed this should not pose a problem!
        import shapely

        if environment_tools.check_wntr() is None:
            feedback.setProgressText("Unpacking WNTR")
            environment_tools.install_wntr()

        try:
            import wntr
        except ImportError as e:
            raise QgsProcessingException(e) from e

        feedback.pushDebugInfo("WNTR version: " + wntr.__version__)

        # PREPARE WN_GIS GEODATAFRAMES
        if feedback.isCanceled():
            return {}
        feedback.setProgress(10)
        feedback.setProgressText("Creating WNTR model")

        options_hydraulic = self.parameterAsMatrix(parameters, self.OPTIONSHYDRAULIC, context)
        options_time = self.parameterAsMatrix(parameters, self.OPTIONSTIME, context)

        node_link_types = {
            "JUNCTIONS": "Junction",
            "TANKS": "Tank",
            "RESERVOIRS": "Reservoir",
            "PIPES": "Pipe",
            "PUMPS": "Pump",
            "VALVES": "Valve",
        }

        # ! this doesn't seem to be working
        if self.validateInputCrs(parameters, context) is not True:
            feedback.pushWarning("Warning - CRS of inputs don't match - this could cause unexpected problems")

        gdf_inputs = {}
        for i in ["JUNCTIONS", "TANKS", "RESERVOIRS", "PIPES", "PUMPS", "VALVES"]:
            lyr = self.parameterAsVectorLayer(parameters, i, context)
            if lyr is None:
                continue
            crs = lyr.crs()
            gdf = gpd.GeoDataFrame.from_features(lyr.getFeatures())
            gdf.dropna(how="all", axis=1, inplace=True)
            if len(gdf) == 0:
                continue
            if i in ("JUNCTIONS", "TANKS", "RESERVOIRS"):
                gdf["node_type"] = node_link_types[i]
            else:
                gdf["link_type"] = node_link_types[i]
                gdf["geometry"] = gdf["geometry"].line_merge()  # shapefiles are multi line strings
            # TODO make aboe and below lines only run on shapefiles, not all inputs
            gdf.rename(columns=self._shapefile_field_name_map(), inplace=True, errors="ignore")
            feedback.pushInfo(str(gdf.columns))
            gdf.set_index("name", inplace=True)
            gdf.index.rename(None, inplace=True)
            gdf_inputs[str.lower(i)] = gdf

        # START WNTR MODEL

        self.wn = wntr.network.WaterNetworkModel()

        # PREPARE PATTERNS AND CURVES
        self.name_increment = 1  # first pattern must be '2' as default pattern in wntr is '1'

        def _add_curve(curve_string, curve_type):
            if curve_string:
                self.name_increment = self.name_increment + 1
                name = str(self.name_increment)
                curvelist = ast.literal_eval(curve_string)
                self.wn.add_curve(name=name, curve_type=curve_type, xy_tuples_list=curvelist)
                return name
            return None

        def _add_pattern(pattern_string):
            if pattern_string:
                self.name_increment = self.name_increment + 1
                name = str(self.name_increment)
                patternlist = ast.literal_eval(pattern_string)
                self.wn.add_pattern(name=name, pattern=patternlist)
                return name
            return None

        if "junctions" in gdf_inputs and "demand_pattern" in gdf_inputs["junctions"]:
            gdf_inputs["junctions"]["demand_pattern_name"] = gdf_inputs["junctions"]["demand_pattern"].apply(
                _add_pattern
            )
        if "reservoirs" in gdf_inputs and "vol_curve" in gdf_inputs["reservoirs"]:
            gdf_inputs["reservoirs"]["head_pattern_name"] = gdf_inputs["reservoirs"]["head_pattern"].apply(_add_pattern)
        if "tanks" in gdf_inputs and "vol_curve" in gdf_inputs["tanks"]:
            gdf_inputs["tanks"]["vol_curve_name"] = gdf_inputs["tanks"]["vol_curve"].apply(
                _add_curve, curve_type="VOLUME"
            )
        if "pumps" in gdf_inputs and "pump_curve" in gdf_inputs["pumps"]:
            gdf_inputs["pumps"]["pump_curve_name"] = gdf_inputs["pumps"]["pump_curve"].apply(
                _add_curve, curve_type="HEAD"
            )
        if "pumps" in gdf_inputs and "speed_pattern" in gdf_inputs["pumps"]:
            gdf_inputs["pumps"]["speed_pattern_name"] = gdf_inputs["pumps"]["speed_pattern"].apply(_add_pattern)
        if "pumps" in gdf_inputs and "energy_pattern" in gdf_inputs["pumps"]:
            gdf_inputs["pumps"]["energy_pattern_name"] = gdf_inputs["pumps"]["energy_pattern"].apply(_add_pattern)

        if feedback.isCanceled():
            return {}
        # try:  # try loading nodes and links into wntr
        self.wn.from_gis(gdf_inputs)
        # except Exception as e:
        #    raise QgsProcessingException("Error loading network: " + str(e)) from e

        # ADD DEMANDS - wntr 1.2 doesn't handle this automatically
        if gdf_inputs.get("junctions") is not None:
            for junction_name, junction in self.wn.junctions():
                junction.demand_timeseries_list.clear()
                try:
                    base_demand = gdf_inputs["junctions"].at[junction_name, "base_demand"]
                    pattern_name = gdf_inputs["junctions"].at[
                        junction_name, "demand_pattern_name"
                    ]  # 'None' if no pattern
                    if base_demand:
                        junction.add_demand(base=base_demand, pattern_name=pattern_name)
                except KeyError:
                    pass

        # ADD OPTIONS

        options_hydraulic_dict = {}
        for i in range(0, len(options_hydraulic), 2):
            options_hydraulic_dict[options_hydraulic[i]] = options_hydraulic[i + 1]
        self.wn.options.hydraulic = wntr.network.options.HydraulicOptions(**options_hydraulic_dict)

        options_time_dict = {}
        for i in range(0, len(options_time), 2):
            options_time_dict[options_time[i]] = options_time[i + 1]
        self.wn.options.time = wntr.network.options.TimeOptions(**options_time_dict)

        if feedback.isCanceled():
            return {}
        feedback.pushInfo("WNTR model created. Model contains:")
        feedback.pushInfo(str(self.wn.describe(level=0)))

        # RUN SIMULATION
        feedback.setProgress(25)
        feedback.setProgressText("Running Simulation")

        # create logger
        logger = logging.getLogger("wntr")
        ch = LoggingHandler(feedback)
        ch.setLevel(logging.WARNING)
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        tempfolder = QgsProcessingUtils.tempFolder() + "/wntr"

        try:
            sim = wntr.sim.EpanetSimulator(self.wn)
            results = sim.run_sim(file_prefix=tempfolder)  # by default, this runs EPANET 2.2.0
        except Exception as e:
            raise QgsProcessingException("Error running model: " + str(e)) from e

        if feedback.isCanceled():
            return {}
        feedback.setProgress(50)
        feedback.setProgressText("Simulation completed.")

        # PROCESS SIMULATION RESULTS
        outputs = {}

        f = QVariant.Double

        possibleparams = {
            "nodes": {
                "demand": f,
                "head": f,
                "pressure": f,
                "quality": f,
            },
            "links": {
                "flowrate": f,
                "headloss": f,
                "velocity": f,
            },
        }
        combined_input_gdf = {
            "nodes": pd.concat([gdf_inputs.get("junctions"), gdf_inputs.get("reservoirs"), gdf_inputs.get("tanks")]),
            "links": pd.concat([gdf_inputs.get("pipes"), gdf_inputs.get("valves"), gdf_inputs.get("pumps")]),
        }
        input_param = {"nodes": self.OUTPUTNODES, "links": self.OUTPUTLINKS}

        for nodeorlink, result in {"nodes": results.node, "links": results.link}.items():
            feedback.setProgressText("Preparing output layer for " + nodeorlink)

            resultparamstouse = [p for p in result if p in possibleparams[nodeorlink]]
            fields = QgsFields()
            fields.append(QgsField("name", QVariant.String))
            for p in resultparamstouse:
                fields.append(QgsField(p, QVariant.List, subType=possibleparams[nodeorlink][p]))

            (sink, outputs[input_param[nodeorlink]]) = self.parameterAsSink(
                parameters,
                input_param[nodeorlink],
                context,
                fields,
                QgsWkbTypes.Point if nodeorlink == "nodes" else QgsWkbTypes.LineString,
                crs,
            )
            g = QgsGeometry()
            combined_input_gdf[nodeorlink].reset_index(inplace=True, names="name")
            for row in combined_input_gdf[nodeorlink].itertuples(index=False):
                g.fromWkb(shapely.to_wkb(row.geometry))
                f = QgsFeature()
                f.setGeometry(g)
                atts = [result[p][row.name].to_list() for p in resultparamstouse]
                f.setAttributes([row.name, *atts])
                sink.addFeature(
                    f,
                    QgsFeatureSink.FastInsert,
                )
            if feedback.isCanceled():
                return {}
            feedback.setProgress(feedback.progress() + 20)

        feedback.setProgressText("Finished layer creation")

        # PREPARE TO LOAD LAYER STYLES IN MAIN THREAD ONCE FINISHED

        for outputname, lyr_id in outputs.items():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(outputname)
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])

        return outputs

    def _shapefile_field_name_map(self):
        """
        Return a map (dictionary) of tuncated shapefile field names to
        valid base WaterNetworkModel attribute names

        Esri Shapefiles truncate field names to 10 characters. The field name
        map links truncated shapefile field names to complete (and ofen longer)
        WaterNetworkModel attribute names.  This assumes that the first 10
        characters of each attribute name are unique.

        Returns
        -------
        field_name_map : dict
            Map (dictionary) of valid base shapefile field names to
            WaterNetworkModel attribute names
        """

        valid_names = wntrqgis.fields.namesPerLayer

        name_map = {}
        for attributes in valid_names.values():
            name_map.update({attribute[:10]: attribute for attribute in attributes})
        return name_map


class LoggingHandler(logging.StreamHandler):
    def __init__(self, feedback):
        logging.StreamHandler.__init__(self)
        self.feedback = feedback

    def emit(self, record):
        msg = self.format(record)
        self.feedback.pushWarning(msg)
