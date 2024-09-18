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

from pathlib import Path

from qgis import processing
from qgis.core import (
    QgsExpressionContextUtils,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsJsonUtils,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFile,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication, QVariant

try:
    import wntr

    NOWNTR = False
except:
    NOWNTR = True
import json
import os

try:
    import pandas as pd

    NOPANDAS = False
except:
    NOPANDAS = True


class ImportInp(QgsProcessingAlgorithm):
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.

    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT = "INPUT"
    CRS = "CRS"
    OUTPUTNODES = "OUTPUTNODES"
    OUTPUTLINKS = "OUTPUTLINKS"

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return ImportInp()

    def name(self):
        return "importinp"

    def displayName(self):
        return self.tr("Import from Epanet INP file")

    def group(self):
        return ""

    def groupId(self):
        return ""

    def shortHelpString(self):
        return self.tr("Example algorithm short description")

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT,
                "Epanet Input File (.inp)",
                behavior=QgsProcessingParameterFile.File,
                extension="inp",
                defaultValue=None,
            )
        )
        self.addParameter(QgsProcessingParameterCrs(self.CRS, "CRS", defaultValue="EPSG:4326"))

        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUTNODES, self.tr("Nodes")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUTLINKS, self.tr("Links")))

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        if NOWNTR:
            raise QgsProcessingException("WNTR is not installed")
        if NOPANDAS:
            raise QgsProcessingException("Pandas is not installed")

        # Retrieve the feature source and sink. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        source = self.parameterAsFile(parameters, self.INPUT, context)
        crs = self.parameterAsCrs(parameters, self.CRS, context)

        # If source was not found, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSourceError method to return a standard
        # helper text for when a source cannot be evaluated
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        wn = wntr.network.read_inpfile(source)

        wn_base_dict = wn.to_dict()
        wn_base_dict.pop("nodes", None)
        wn_base_dict.pop("links", None)
        # print(json.dumps(wn_base_dict, sort_keys=True, indent=4))
        try:
            wn_gis = wntr.network.to_gis(wn)
        except ModuleNotFoundError as e:
            raise QgsProcessingException("WNTR dependencies not installed: " + str(e)) from e
        wn_gis.set_crs(crs.toProj())
        wn_gis.junctions["base_demand"] = wn.query_node_attribute("base_demand", node_type=wntr.network.model.Junction)
        nodes = pd.concat([wn_gis.junctions, wn_gis.tanks, wn_gis.reservoirs])
        links = pd.concat([wn_gis.pipes, wn_gis.pumps, wn_gis.valves])

        nodefieldlist = {
            "name": QVariant.String,
            "node_type": QVariant.String,
            "elevation": QVariant.Double,
            "base_demand": QVariant.Double,  # Warrrrrnninnng
            "emitter_coefficient": QVariant.Double,
            "initial_quality": QVariant.Double,
            "minimum_pressure": QVariant.Double,
            "required_pressure": QVariant.Double,
            "pressure_exponent": QVariant.Double,
            "tag": QVariant.String,
            "init_level": QVariant.Double,
            "min_level": QVariant.Double,
            "max_level": QVariant.Double,
            "diameter": QVariant.Double,
            "min_volvol_curve_name": QVariant.String,
            "overflow": QVariant.Bool,
            "mixing_fraction": QVariant.Double,
            "mixing_model": QVariant.String,
            "bulk_coeff": QVariant.Double,
            "base_head": QVariant.Double,
            "head_pattern_name": QVariant.String,
        }
        nodefields = QgsFields()
        for x, y in nodefieldlist.items():
            nodefields.append(QgsField(x, y))

        (nodessink, nodes_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUTNODES, context, nodefields, QgsWkbTypes.Point, crs
        )
        nodessink.addFeatures(QgsJsonUtils.stringToFeatureList(nodes.to_json(), nodefields), QgsFeatureSink.FastInsert)

        pipeslayer = QgsVectorLayer(links.to_json(), "links", "ogr")
        (pipessink, pipes_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUTLINKS, context, pipeslayer.fields(), pipeslayer.wkbType(), crs
        )
        pipessink.addFeatures(pipeslayer.getFeatures(), QgsFeatureSink.FastInsert)

        if context.willLoadLayerOnCompletion(nodes_dest_id):
            context.layerToLoadOnCompletionDetails(nodes_dest_id).setPostProcessor(InputNodesStyler())
            feedback.pushInfo("planning to load style")

        # Save options to project
        try:
            QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(), "wntr-options", wn.options.to_dict())
        except Exception:
            feedback.pushInfo("Could not save water network options to project file")

        return {self.OUTPUTNODES: nodes_dest_id, self.OUTPUTLINKS: pipes_dest_id}


class InputNodesStyler(QgsProcessingLayerPostProcessorInterface):
    def postProcessLayer(self, layer, context, feedback):
        feedback.pushInfo("about to load")
        if layer.isValid():
            # layer.loadNamedStyle("C:\\Users\\amcbride\\Downloads\\node-out-style.qml")
            layer.loadNamedStyle(Path(__file__).parent / "resources" / "styles" / "node-in-style.qml")
            # layer.loadNamedStyle(
            #    os.path.join(
            #        os.path.abspath(os.path.dirname(__file__)),
            #        'node-in-style.qml'))
            feedback.pushInfo(
                "Node style loaded from: "
                + os.path.join(os.path.abspath(os.path.dirname(__file__)), "node-in-style.qml")
            )
