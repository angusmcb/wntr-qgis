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

import logging
from pathlib import Path

from qgis.core import (
    QgsExpressionContextUtils,
    QgsFeatureSink,
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
)
from qgis.PyQt.QtCore import QCoreApplication

try:
    import wntr

    NOWNTR = False
except:
    NOWNTR = True


try:
    import pandas as pd

    NOPANDAS = False
except:
    NOPANDAS = True

try:
    import geopandas as gpd

    NOGEOPANDAS = False
except:
    NOGEOPANDAS = True


class RunSimulation(QgsProcessingAlgorithm):
    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

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

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return RunSimulation()

    def name(self):
        return "run"

    def displayName(self):
        return self.tr("Run Simulation")

    def group(self):
        return ""

    def groupId(self):
        return ""

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and
        the parameters and outputs associated with it..
        """
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
        """
        Here is where the processing itself takes place.
        """
        if NOWNTR:
            raise QgsProcessingException("WNTR is not installed")
        if NOPANDAS:
            raise QgsProcessingException("Pandas is not installed")
        if NOGEOPANDAS:
            raise QgsProcessingException("Geopandas is not installed")

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
        crs = ""

        gdf_inputs = {}
        for i in ["JUNCTIONS", "TANKS", "RESERVOIRS", "PIPES", "PUMPS", "VALVES"]:
            lyr = self.parameterAsVectorLayer(parameters, i, context)
            if lyr is None:
                feedback.pushInfo("Not adding " + str.lower(i))
                continue
            crs = lyr.crs()
            gdf = gpd.GeoDataFrame.from_features(lyr.getFeatures())
            gdf.dropna(how="all", axis=1, inplace=True)
            if len(gdf) == 0:
                feedback.pushInfo("Not adding " + str.lower(i))
                continue
            if i in ("JUNCTIONS", "TANKS", "RESERVOIRS"):
                gdf["node_type"] = node_link_types[i]
            else:
                gdf["link_type"] = node_link_types[i]
            gdf.set_index("name", inplace=True)
            gdf.index.rename(None, inplace=True)
            gdf_inputs[str.lower(i)] = gdf
            feedback.pushInfo("Adding " + str(len(gdf)) + " " + str.lower(i))

        try:
            wn = wntr.network.from_gis(gdf_inputs)
        except Exception as e:
            raise QgsProcessingException("Error loading network: " + str(e)) from e

        # Add demands!
        if gdf_inputs.get("junctions") is not None:
            for junction_name, junction in wn.junctions():
                try:
                    base_demand = gdf_inputs["junctions"].at[junction_name, "base_demand"]
                    if base_demand:
                        junction.add_demand(base=base_demand, pattern_name="1")
                        feedback.pushInfo("Added demand to " + junction_name + " - " + str(base_demand))
                except KeyError:
                    pass

        options_hydraulic_dict = {}
        for i in range(0, len(options_hydraulic), 2):
            options_hydraulic_dict[options_hydraulic[i]] = options_hydraulic[i + 1]
        wn.options.hydraulic = wntr.network.options.HydraulicOptions(**options_hydraulic_dict)

        options_time_dict = {}
        for i in range(0, len(options_time), 2):
            options_time_dict[options_time[i]] = options_time[i + 1]
        wn.options.time = wntr.network.options.TimeOptions(**options_time_dict)

        feedback.pushInfo("Model loaded.")
        feedback.pushCommandInfo(str(wn.describe(level=0)))

        wntr.network.write_inpfile(wn, "outputfile.inp")
        # feedback.pushInfo('Model options:\n{}'.format(str(wn.options)))

        # wn.options.report.report_filename = 'C:\\Users\\amcbride\\Downloads\\epa-report.txt'
        # wn.options.report.status = 'YES'
        # wn.options.report.summary = 'YES'
        # wn.options.report.links = True
        # wn.options.report.nodes = True

        # create logger
        logger = logging.getLogger("wntr")
        ch = LoggingHandler(feedback)
        ch.setLevel(logging.WARNING)
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        sim = wntr.sim.EpanetSimulator(wn)
        try:
            results = sim.run_sim()  # by default, this runs EPANET 2.2.0
        except Exception as e:
            raise QgsProcessingException("Error running model: " + str(e))

        feedback.pushInfo("Model has run. Preparing outputs.")
        results_dfs = {"nodes": None, "links": None}
        for type, result in {"nodes": results.node, "links": results.link}.items():
            for param_name in result.keys():
                feedback.pushInfo("Processing results for " + param_name)
                param_df = result[param_name].reset_index(names="time")
                param_long_df = param_df.melt(id_vars="time", var_name="name", value_name=param_name)
                # merge all our results into one dataframe
                if results_dfs[type] is not None:
                    results_dfs[type] = results_dfs[type].merge(param_long_df, on=["name", "time"])
                else:
                    # For first parameter, results dataframe will be empty so
                    # nothing to merge with
                    results_dfs[type] = param_long_df
            # Add a column for time from unix epoch (1 jan 1970) for qgis
            # temporal controller
            results_dfs[type]["datetime"] = pd.to_datetime(results_dfs[type]["time"], unit="s")
            feedback.pushDebugInfo(results_dfs[type].info(verbose=True))

        inputnodes_gdf = pd.concat([gdf_inputs.get("junctions"), gdf_inputs.get("reservoirs"), gdf_inputs.get("tanks")])
        inputlinks_gdf = pd.concat([gdf_inputs.get("pipes"), gdf_inputs.get("valves"), gdf_inputs.get("pumps")])

        inputlinks_gdf.reset_index(inplace=True, names="name")
        inputnodes_gdf.reset_index(inplace=True, names="name")

        feedback.pushDebugInfo(inputnodes_gdf.info(verbose=True))

        outputnodes_df = pd.merge(inputnodes_gdf, results_dfs["nodes"], on="name")
        outputlinks_df = pd.merge(inputlinks_gdf, results_dfs["links"], on="name")

        feedback.pushInfo("Finished processing model outputs.")
        # feedback.pushDebugInfo(outputnodes_df.info(verbose=True))
        # feedback.pushDebugInfo(str(outputnodes_df.head(10)))
        # feedback.pushDebugInfo(outputlinks_df.info(verbose=True))
        # feedback.pushDebugInfo(str(outputlinks_df.head(10)))
        nodeoutputfilename = QgsProcessingUtils.generateTempFilename("nodeout.gpkg")
        linkoutputfilename = QgsProcessingUtils.generateTempFilename("linkout.gpkg")

        outputnodes_df.to_file(nodeoutputfilename, driver="GPKG")
        feedback.pushInfo(f"Nodes output to: {nodeoutputfilename}")

        outputlinks_df.to_file(linkoutputfilename, driver="GPKG")
        feedback.pushInfo(f"Links output to: {linkoutputfilename}")

        junctionslayer = QgsVectorLayer(nodeoutputfilename, "nodes", "ogr")
        # junctionslayer = QgsVectorLayer(outputnodes_df.to_json(),"nodes","ogr")
        (junctionssink, junctions_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUTNODES, context, junctionslayer.fields(), junctionslayer.wkbType(), crs
        )
        junctionssink.addFeatures(junctionslayer.getFeatures(), QgsFeatureSink.FastInsert)

        pipeslayer = QgsVectorLayer(linkoutputfilename, "links", "ogr")
        (pipessink, pipes_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUTLINKS, context, pipeslayer.fields(), pipeslayer.wkbType(), crs
        )
        pipessink.addFeatures(pipeslayer.getFeatures(), QgsFeatureSink.FastInsert)

        for type, lyr_id in {"NODE": junctions_dest_id, "LINK": pipes_dest_id}.items():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(type)
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])

        return {self.OUTPUTNODES: junctions_dest_id, self.OUTPUTLINKS: pipes_dest_id}


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None
    layertype = None

    def postProcessLayer(self, layer, context, feedback):
        print(layer.name())
        if not isinstance(layer, QgsVectorLayer):
            return
        layer.loadNamedStyle(
            str(Path(__file__).parent.parent / "resources" / "styles" / (self.layertype + "-RESULTS.qml"))
        )

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
        self.feedback.pushConsoleInfo(msg)
