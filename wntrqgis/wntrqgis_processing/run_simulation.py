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

from qgis import processing
from qgis.core import (
    QgsExpressionContextUtils,
    QgsFeatureSink,
    QgsJsonExporter,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFile,
    QgsProcessingParameterMatrix,
    QgsProcessingParameterVectorLayer,
    QgsProcessingUtils,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication

try:
    import wntr
except:
    NOWNTR = True
try:
    import pandas as pd
except:
    NOPANDAS = True
try:
    import geopandas
except:
    NOGEOPANDAS = True


class RunSimulation(QgsProcessingAlgorithm):
    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT = "INPUT"
    INPUTNODES = "INPUTNODES"
    INPUTLINKS = "INPUTLINKS"

    OUTPUTNODES = "OUTPUTNODES"
    OUTPUTLINKS = "OUTPUTLINKS"

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
        return self.tr("Build and Run Model")

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
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT,
                "Epanet Input File (.inp)",
                behavior=QgsProcessingParameterFile.File,
                extension="inp",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(self.INPUTNODES, "Input Nodes", types=[QgsProcessing.TypeVectorPoint])
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(self.INPUTLINKS, "Input Links", types=[QgsProcessing.TypeVectorLine])
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
        options = QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable("wntr-options")

        optionslist = default_options
        if options:
            for i in options.keys():
                optionslist[i] = []
                for x, y in options[i].items():
                    optionslist[i].append(x)
                    optionslist[i].append(y)

        param = QgsProcessingParameterMatrix(
            "time_settings",
            "Time Settings",
            numberRows=1,
            hasFixedNumberRows=True,
            headers=["Setting Name", "Setting Value"],
            defaultValue=optionslist["time"],
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        param = QgsProcessingParameterMatrix(
            "hydraulic_settings",
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

        # Retrieve the feature source and sink. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        source = self.parameterAsFile(parameters, self.INPUT, context)

        inputnodes = self.parameterAsVectorLayer(parameters, self.INPUTNODES, context)
        inputlinks = self.parameterAsVectorLayer(parameters, self.INPUTLINKS, context)

        # If source was not found, throw an exception to indicate that the
        # algorithm encountered a fatal error. The exception text can be
        # any string, but in this case we use the pre-built
        # invalidSourceError method to return a standard
        # helper text for when a source cannot be evaluated
        # if source is None:
        #   raise QgsProcessingException(self.invalidSourceError(parameters,
        #       self.INPUT))

        # Prepare Inputs for Water Network Model

        # Convert input qgisvectorlayers into geodataframes

        nodeinputfilename = QgsProcessingUtils.generateTempFilename("nodein.gpkg")
        QgsVectorFileWriter.writeAsVectorFormatV3(
            inputnodes,
            nodeinputfilename,
            QgsProject.instance().transformContext(),
            QgsVectorFileWriter.SaveVectorOptions(),
        )

        inputnodes_df = geopandas.GeoDataFrame.from_file(nodeinputfilename)

        linkinputfilename = QgsProcessingUtils.generateTempFilename("linkin.gpkg")
        QgsVectorFileWriter.writeAsVectorFormatV3(
            inputlinks,
            linkinputfilename,
            QgsProject.instance().transformContext(),
            QgsVectorFileWriter.SaveVectorOptions(),
        )

        inputlinks_df = geopandas.GeoDataFrame.from_file(linkinputfilename)
        """

        inputnodes_df = geopandas.GeoDataFrame.from_features(
            inputnodes.getFeatures().__geo_interface__,
            # columns=['name', 'node_type', 'elevation', 'base_head'] + ['geometry']
        ).drop(
            'fid', axis=1, errors='ignore')

        inputlinks_df = geopandas.GeoDataFrame.from_features(
            jsonexporter.exportFeatures(inputlinks.getFeatures()),
            columns=inputlinks.fields().names() + ['geometry']).drop(
            'fid', axis=1, errors='ignore')
        """

        if len(inputnodes_df) == 0:
            raise QgsProcessingException(self.tr("The input node layer must contain at least two points."))
        if len(inputlinks_df) == 0:
            raise QgsProcessingException(self.tr("The input links layer must contain at least one line."))

        # Split node and link geodataframes into their component parts
        wn_gis_inputs = {
            "junctions": inputnodes_df[inputnodes_df["node_type"] == "Junction"],
            "tanks": inputnodes_df[inputnodes_df["node_type"] == "Tank"],
            "reservoirs": inputnodes_df[inputnodes_df["node_type"] == "Reservoir"],
            "pipes": inputlinks_df[inputlinks_df["link_type"] == "Pipe"],
            "valves": inputlinks_df[inputlinks_df["link_type"] == "Valve"],
            "pumps": inputlinks_df[inputlinks_df["link_type"] == "Pump"],
        }
        feedback.pushInfo(wn_gis_inputs["reservoirs"].info())
        for n, df in wn_gis_inputs.items():
            df.set_index("name", inplace=True)
            df.index.rename(None, inplace=True)
            feedback.pushInfo(f"Loading into model: {len(df)} {n}")

        try:
            wn = wntr.network.from_gis(wn_gis_inputs)
        except Exception as e:
            raise QgsProcessingException("Error running model: " + str(e))

        # Add all non-spatial settings from base .inp file
        wn_base = wntr.network.read_inpfile(source)
        wn_base_dict = wn_base.to_dict()
        wn_base_dict.pop("nodes", None)
        wn_base_dict.pop("links", None)
        wn.from_dict(wn_base_dict)

        feedback.pushInfo("Model loaded.")
        feedback.pushCommandInfo(str(wn.describe(level=0)))
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

        outputnodes_df = pd.merge(inputnodes_df, results_dfs["nodes"], on="name")
        outputlinks_df = pd.merge(inputlinks_df, results_dfs["links"], on="name")

        feedback.pushInfo("Finished processing model outputs.")
        feedback.pushDebugInfo(outputnodes_df.info(verbose=True))
        feedback.pushDebugInfo(str(outputnodes_df.head(10)))
        feedback.pushDebugInfo(outputlinks_df.info(verbose=True))
        feedback.pushDebugInfo(str(outputlinks_df.head(10)))
        nodeoutputfilename = QgsProcessingUtils.generateTempFilename("nodeout.gpkg")
        linkoutputfilename = QgsProcessingUtils.generateTempFilename("linkout.gpkg")

        outputnodes_df.to_file(nodeoutputfilename, driver="GPKG")
        feedback.pushInfo(f"Nodes output to: {nodeoutputfilename}")

        outputlinks_df.to_file(linkoutputfilename, driver="GPKG")
        feedback.pushInfo(f"Links output to: {linkoutputfilename}")

        junctionslayer = QgsVectorLayer(nodeoutputfilename, "nodes", "ogr")
        # junctionslayer = QgsVectorLayer(outputnodes_df.to_json(),"nodes","ogr")
        (junctionssink, junctions_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUTNODES, context, junctionslayer.fields(), inputnodes.wkbType(), inputnodes.crs()
        )
        junctionssink.addFeatures(junctionslayer.getFeatures(), QgsFeatureSink.FastInsert)

        pipeslayer = QgsVectorLayer(linkoutputfilename, "links", "ogr")
        (pipessink, pipes_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUTLINKS, context, pipeslayer.fields(), inputlinks.wkbType(), inputlinks.crs()
        )
        pipessink.addFeatures(pipeslayer.getFeatures(), QgsFeatureSink.FastInsert)

        if context.willLoadLayerOnCompletion(junctions_dest_id):
            context.layerToLoadOnCompletionDetails(junctions_dest_id).setPostProcessor(NodesStyler())

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return {self.OUTPUTNODES: junctions_dest_id, self.OUTPUTLINKS: pipes_dest_id}


class NodesStyler(QgsProcessingLayerPostProcessorInterface):
    def postProcessLayer(self, layer, context, feedback):
        if layer.isValid():
            layer.loadNamedStyle(Path(__file__).parent / "resources" / "styles" / "node-out-style.qml")
            feedback.pushInfo("Node style loaded")


class LoggingHandler(logging.StreamHandler):
    def __init__(self, feedback):
        logging.StreamHandler.__init__(self)
        self.feedback = feedback

    def emit(self, record):
        msg = self.format(record)
        self.feedback.pushConsoleInfo(msg)
