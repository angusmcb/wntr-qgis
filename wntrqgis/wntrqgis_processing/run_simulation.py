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

import ast
import logging
from pathlib import Path

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
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterMatrix,
    QgsProcessingParameterVectorLayer,
    QgsProcessingUtils,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication, QMetaType, QVariant

from wntrqgis.checkDependencies import checkDependencies


class RunSimulation(QgsProcessingAlgorithm):
    OPTIONSHYDRAULIC = "OPTIONSHYDRAULIC"
    OPTIONSTIME = "OPTIONSTIME"

    INPUTNODES = "INPUTNODES"
    INPUTLINKS = "INPUTLINKS"

    JUNCTIONS = "JUNCTIONS"
    TANKS = "TANKS"
    RESERVOIRS = "RESERVOIRS"
    PIPES = "PIPES"
    PUMPS = "PUMPS"
    VALVES = "VALVES"

    OUTPUTNODES = "OUTPUTNODES"
    OUTPUTLINKS = "OUTPUTLINKS"
    post_processors = dict()
    wn = None
    name_increment = 0

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return RunSimulation()

    def name(self):
        return "run"

    def displayName(self):
        return self.tr("Run Simulation")

    def shortHelpString(self):
        return self.tr("Example algorithm short description")

    def initAlgorithm(self, config=None):
        default_layers = QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable("wntr_layers")
        if default_layers is None:
            default_layers = {}

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.JUNCTIONS,
                "Junctions",
                types=[QgsProcessing.TypeVectorPoint],
                defaultValue=default_layers.get("JUNCTIONS"),
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
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

        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUTNODES, self.tr("Output Nodes")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUTLINKS, self.tr("Output Links")))

        default_options = {
            "time": {
                "duration": 0.0,
                "hydraulic_timestep": 3600,
                "quality_timestep": 360,
                "rule_timestep": 360,
                "pattern_timestep": 3600,
                "pattern_start": 0.0,
                "report_timestep": 3600,
                "report_start": 0.0,
                "start_clocktime": 0.0,
                "statistic": "NONE",
                "pattern_interpolation": False,
            },
            "hydraulic": {
                "headloss": "H-W",
                "hydraulics": None,
                "hydraulics_filename": None,
                "viscosity": 1.0,
                "specific_gravity": 1.0,
                "pattern": "1",
                "demand_multiplier": 1.0,
                "demand_model": "DDA",
                "minimum_pressure": 0.0,
                "required_pressure": 0.07,
                "pressure_exponent": 0.5,
                "emitter_exponent": 0.5,
                "trials": 200,
                "accuracy": 0.001,
                "unbalanced": "STOP",
                "unbalanced_value": None,
                "checkfreq": 2,
                "maxcheck": 10,
                "damplimit": 0.0,
                "headerror": 0.0,
                "flowchange": 0.0,
                "inpfile_units": "GPM",
                "inpfile_pressure_units": None,
            },
            "report": {
                "pagesize": None,
                "report_filename": None,
                "status": "NO",
                "summary": "YES",
                "energy": "NO",
                "nodes": False,
                "links": False,
                "report_params": {
                    "elevation": False,
                    "demand": True,
                    "head": True,
                    "pressure": True,
                    "quality": True,
                    "length": False,
                    "diameter": False,
                    "flow": True,
                    "velocity": True,
                    "headloss": True,
                    "position": False,
                    "setting": False,
                    "reaction": False,
                    "f-factor": False,
                },
                "param_opts": {
                    "elevation": {},
                    "demand": {},
                    "head": {},
                    "pressure": {},
                    "quality": {},
                    "length": {},
                    "diameter": {},
                    "flow": {},
                    "velocity": {},
                    "headloss": {},
                    "position": {},
                    "setting": {},
                    "reaction": {},
                    "f-factor": {},
                },
            },
            "quality": {
                "parameter": "NONE",
                "trace_node": None,
                "chemical_name": "CHEMICAL",
                "diffusivity": 1.0,
                "tolerance": 0.01,
                "inpfile_units": "mg/L",
            },
            "reaction": {
                "bulk_order": 1.0,
                "wall_order": 1.0,
                "tank_order": 1.0,
                "bulk_coeff": 0.0,
                "wall_coeff": 0.0,
                "limiting_potential": None,
                "roughness_correl": None,
            },
            "energy": {"global_price": 0, "global_pattern": None, "global_efficiency": None, "demand_charge": None},
            "graphics": {
                "dimensions": None,
                "units": "NONE",
                "offset": None,
                "image_filename": None,
                "map_filename": None,
            },
            "user": {},
        }
        options = QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable("wntr_options")

        optionslist = default_options
        if options:
            for i in options.keys():
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

    def processAlgorithm(self, parameters, context, feedback):
        # PREPARE IMPORTS
        # imports are here in case wntr is installed on qgis startup, but also so we can easily provide exceptions

        feedback.setProgressText("Checking dependencies")
        try:
            import geopandas as gpd
        except ImportError as e:
            raise QgsProcessingException("Geopandas is not installed") from e
        import pandas as pd  # if geopadas installed this should not pose a problem!
        import shapely

        try:
            import wntr
        except ImportError as e:
            raise QgsProcessingException("WNTR is not installed") from e

        feedback.pushDebugInfo("WNTR version: " + wntr.__version__)

        # PREPARE WN_GIS GEODATAFRAMES
        if feedback.isCanceled():
            return {}
        feedback.setProgress(5)
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
            else:
                return None

        def _add_pattern(pattern_string):
            if pattern_string:
                self.name_increment = self.name_increment + 1
                name = str(self.name_increment)
                patternlist = ast.literal_eval(pattern_string)
                self.wn.add_pattern(name=name, pattern=patternlist)
                return name
            else:
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
        try:  # try loading nodes and links into wntr
            self.wn.from_gis(gdf_inputs)
        except Exception as e:
            raise QgsProcessingException("Error loading network: " + str(e)) from e

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
                        # feedback.pushInfo("Added demand to " + junction_name + " - " + str(pattern_name))
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

        wntr.network.write_inpfile(self.wn, "outputfile.inp")

        # RUN SIMULATION

        if feedback.isCanceled():
            return {}
        feedback.setProgress(25)
        feedback.setProgressText("Running Simulation")

        # create logger
        logger = logging.getLogger("wntr")
        ch = LoggingHandler(feedback)
        ch.setLevel(logging.WARNING)
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        sim = wntr.sim.EpanetSimulator(self.wn)
        try:
            results = sim.run_sim()  # by default, this runs EPANET 2.2.0
        except Exception as e:
            raise QgsProcessingException("Error running model: " + str(e))

        if feedback.isCanceled():
            return {}
        feedback.setProgress(50)
        feedback.setProgressText("Simulation completed.")

        # PROCESS SIMULATION RESULTS
        outputs = {}

        possibleparams = {
            "nodes": {
                "demand": QMetaType.Double,
                "head": QMetaType.Double,
                "pressure": QMetaType.Double,
                "quality": QMetaType.Double,
            },
            "links": {
                "flowrate": QMetaType.Double,
                "headloss": QMetaType.Double,
                "velocity": QMetaType.Double,
            },
        }
        combinedInputGdf = {
            "nodes": pd.concat([gdf_inputs.get("junctions"), gdf_inputs.get("reservoirs"), gdf_inputs.get("tanks")]),
            "links": pd.concat([gdf_inputs.get("pipes"), gdf_inputs.get("valves"), gdf_inputs.get("pumps")]),
        }
        inputParam = {"nodes": self.OUTPUTNODES, "links": self.OUTPUTLINKS}

        for type, result in {"nodes": results.node, "links": results.link}.items():
            feedback.setProgressText("Preparing output layer for " + type)

            resultparamstouse = [p for p in result.keys() if p in possibleparams[type].keys()]
            fields = QgsFields()
            fields.append(QgsField("name", QVariant.String))
            for p in resultparamstouse:
                fields.append(QgsField(p, QMetaType.QVariantList, subType=possibleparams[type][p]))

            (sink, outputs[inputParam[type]]) = self.parameterAsSink(
                parameters,
                inputParam[type],
                context,
                fields,
                QgsWkbTypes.Point if type == "nodes" else QgsWkbTypes.LineString,
                crs,
            )
            g = QgsGeometry()
            combinedInputGdf[type].reset_index(inplace=True, names="name")
            for row in combinedInputGdf[type].itertuples(index=False):
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
        """

        combinedInputGdf = {
            "nodes": pd.concat([gdf_inputs.get("junctions"), gdf_inputs.get("reservoirs"), gdf_inputs.get("tanks")]),
            "links": pd.concat([gdf_inputs.get("pipes"), gdf_inputs.get("valves"), gdf_inputs.get("pumps")]),
        }
        inputParam = {"nodes": self.OUTPUTNODES, "links": self.OUTPUTLINKS}
        dest_id = {}
        for type, result in {"nodes": results.node, "links": results.link}.items():
            feedback.pushDebugInfo("Processing results for " + type)
            resultDf = None
            for param_name in result.keys():
                feedback.pushDebugInfo("Processing results for " + param_name)
                param_df = result[param_name].reset_index(names="time")
                param_long_df = param_df.melt(id_vars="time", var_name="name", value_name=param_name)
                # merge all our results into one dataframe
                resultDf = resultDf.merge(param_long_df, on=["name", "time"]) if resultDf is not None else param_long_df
            # Add a column for time from unix epoch (1 jan 1970) for qgis
            # temporal controller
            # results_dfs[type]["datetime"] = pd.to_datetime(results_dfs[type]["time"], unit="s")
            # feedback.pushDebugInfo(results_dfs[type].info(verbose=True))
            combinedInputGdf[type].reset_index(inplace=True, names="name")
            mergedGdf = pd.merge(combinedInputGdf[type][["name", "geometry"]], resultDf, on="name")

            fields = QgsFields()
            fields.append(QgsField("name", QVariant.String))
            for c in resultDf.columns:
                fields.append(QgsField(c, QVariant.Double))
            if type == "nodes":
                fields.append(QgsField("demand_list", QMetaType.QVariantList, subType=QMetaType.Double))

            (sink, dest_id[type]) = self.parameterAsSink(
                parameters,
                inputParam[type],
                context,
                fields,
                QgsWkbTypes.Point if type == "nodes" else QgsWkbTypes.LineString,
                crs,
            )
            g = QgsGeometry()
            for row in mergedGdf.itertuples(index=False):
                g.fromWkb(shapely.to_wkb(row.geometry))
                f = QgsFeature()
                f.setGeometry(g)
                alist = []
                if type == "nodes":
                    alist = result["demand"][row.name].to_list()
                f.setAttributes([row[0], *list(row[2 : len(row)]), alist])
                sink.addFeature(
                    f,
                    QgsFeatureSink.FastInsert,
                )
        ###
        inputnodes_gdf = pd.concat(
            [gdf_inputs.get("junctions"), gdf_inputs.get("reservoirs"), gdf_inputs.get("tanks")]
        ).reset_index(inplace=True, names="name")
        inputlinks_gdf = pd.concat(
            [gdf_inputs.get("pipes"), gdf_inputs.get("valves"), gdf_inputs.get("pumps")]
        ).reset_index(inplace=True, names="name")

        outputnodes_df = pd.merge(inputnodes_gdf[["name", "geometry"]], results_dfs["nodes"], on="name")
        outputlinks_df = pd.merge(inputlinks_gdf[["name", "geometry"]], results_dfs["links"], on="name")

        feedback.pushInfo("Finished processing model outputs.")

        nodefields = QgsFields()
        nodefields.append(QgsField("name", QVariant.String))
        for c in results_dfs["nodes"].columns:
            nodefields.append(QgsField(c, QVariant.Double))

        (junctionssink, junctions_dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUTNODES,
            context,
            nodefields,
            QgsWkbTypes.Point,
            crs,
        )
        g = QgsGeometry()
        for row in outputnodes_df.itertuples(index=False):
            g.fromWkb(shapely.to_wkb(row.geometry))
            f = QgsFeature()
            f.setGeometry(g)
            f.setAttributes([row[0], *list(row[2 : len(row)])])
            junctionssink.addFeature(
                f,
                QgsFeatureSink.FastInsert,
            )


        feedback.pushDebugInfo("about to access json")
        nodejson = outputnodes_df.to_json()
        fields = QgsJsonUtils.stringToFields(nodejson)
        feedback.pushDebugInfo(nodejson)
        (nodessink, nodes_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUTNODES, context, fields, QgsWkbTypes.Point, crs
        )
        feedback.pushDebugInfo("created sink")
        nodessink.addFeatures(QgsJsonUtils.stringToFeatureList(nodejson, fields))



        """

        # PREPARE TO LOAD LAYER STYLES IN MAIN THREAD ONCE FINISHED

        for type, lyr_id in outputs.items():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(type)
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])

        return outputs  # , self.OUTPUTLINKS: pipes_dest_id}


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None
    layertype = None

    def postProcessLayer(self, layer, context, feedback):
        if not isinstance(layer, QgsVectorLayer):
            return
        layer.loadNamedStyle(str(Path(__file__).parent.parent / "resources" / "styles" / (self.layertype + ".qml")))

    @staticmethod
    def create(layertype):
        LayerPostProcessor.instance = LayerPostProcessor()
        LayerPostProcessor.instance.layertype = layertype
        return LayerPostProcessor.instance


class LoggingHandler(logging.StreamHandler):
    def __init__(self, feedback):
        logging.StreamHandler.__init__(self)
        self.feedback = feedback

    def emit(self, record):
        msg = self.format(record)
        self.feedback.pushWarning(msg)
