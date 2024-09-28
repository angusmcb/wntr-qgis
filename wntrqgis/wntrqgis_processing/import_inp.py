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
    QgsFeature,
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

    JUNCTIONS = "JUNCTIONS"
    TANKS = "TANKS"
    RESERVOIRS = "RESERVOIRS"
    PIPES = "PIPES"
    PUMPS = "PUMPS"
    VALVES = "VALVES"

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
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT,
                "Epanet Input File (.inp)",
                behavior=QgsProcessingParameterFile.File,
                extension="inp",
                defaultValue=None,
            )
        )
        self.addParameter(QgsProcessingParameterCrs(self.CRS, "CRS"))

        self.addParameter(QgsProcessingParameterFeatureSink(self.JUNCTIONS, self.tr("Junctions")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.TANKS, self.tr("Tanks")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.RESERVOIRS, self.tr("Reservoirs")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.PIPES, self.tr("Pipes")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.PUMPS, self.tr("Pumps")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.VALVES, self.tr("Valves")))

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

        try:
            wn = wntr.network.read_inpfile(source)
            wn_gis = wntr.network.to_gis(wn)
        except ModuleNotFoundError as e:
            raise QgsProcessingException("WNTR dependencies not installed: " + str(e)) from e
        except Exception as e:
            raise QgsProcessingException("Error loading model: " + str(e))

        feedback.pushInfo("INP file loaded into WNTR. Found the following:")
        feedback.pushCommandInfo(str(wn.describe(level=2)))

        wn_gis.set_crs(crs.toProj())
        wn_gis.junctions["base_demand"] = wn.query_node_attribute("base_demand", node_type=wntr.network.model.Junction)

        try:
            emptylayers = processing.run(
                "wntr:emptymodel",
                {
                    "CRS": crs,
                    "JUNCTIONS": parameters[self.JUNCTIONS],
                    "PIPES": parameters[self.PIPES],
                    "PUMPS": parameters[self.PUMPS],
                    "RESERVOIRS": parameters[self.RESERVOIRS],
                    "TANKS": parameters[self.TANKS],
                    "VALVES": parameters[self.VALVES],
                },
                context=context,
                feedback=None,
                is_child_algorithm=True,
            )
        except:
            raise QgsProcessingException("Couldn't create template layer")

        outputs = {}

        for i, j in {
            "JUNCTIONS": wn_gis.junctions,
            "TANKS": wn_gis.tanks,
            "RESERVOIRS": wn_gis.reservoirs,
            "PIPES": wn_gis.pipes,
            "PUMPS": wn_gis.pumps,
            "VALVES": wn_gis.valves,
        }.items():
            emptylayer = context.getMapLayer(emptylayers[i])

            outputs[i] = emptylayers[i]
            if j.shape[0] > 0:
                j.reset_index(inplace=True, names="name")
                for jsonfeature in QgsJsonUtils.stringToFeatureList(
                    j.to_json(), QgsJsonUtils.stringToFields(j.to_json())
                ):
                    newfeature = QgsFeature()
                    newfeature.setGeometry(jsonfeature.geometry())
                    newfeature.setFields(emptylayer.fields())
                    for fieldname in jsonfeature.fields().names():
                        if fieldname in emptylayer.fields().names():
                            newfeature[fieldname] = jsonfeature[fieldname]
                    emptylayer.dataProvider().addFeature(newfeature)

        # Save options to project
        try:
            QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(), "wntr_options", wn.options.to_dict())
        except Exception:
            feedback.pushInfo("Could not save water network options to project file")

        return outputs
