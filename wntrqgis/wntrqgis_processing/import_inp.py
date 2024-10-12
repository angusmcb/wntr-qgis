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

from typing import ClassVar

from qgis.core import (
    QgsExpressionContextUtils,
    QgsFeature,
    QgsJsonUtils,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFile,
    QgsProject,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication

import wntrqgis.fields
from wntrqgis import environment_tools
from wntrqgis.wntrqgis_processing.LayerPostProcessor import LayerPostProcessor


class ImportInp(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    CRS = "CRS"

    JUNCTIONS = "JUNCTIONS"
    TANKS = "TANKS"
    RESERVOIRS = "RESERVOIRS"
    PIPES = "PIPES"
    PUMPS = "PUMPS"
    VALVES = "VALVES"

    post_processors: ClassVar[dict[str, LayerPostProcessor]] = {}

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):  # noqa N802
        return ImportInp()

    def name(self):
        return "importinp"

    def displayName(self):  # noqa N802
        return self.tr("Import from Epanet INP file")

    def shortHelpString(self):  # noqa N802
        return self.tr("""
            Import all junctions, tanks, reservoirs, pipes, pumps and valves from an EPANET inp file.
            This will also import all of the options from the .inp file.
            All values will be in SI units (metres, kg, seconds, m3/s, etc).
            """)

    def initAlgorithm(self, config=None):  # noqa N802
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
            QgsProcessingParameterCrs(self.CRS, self.tr("Coordinate Reference System (CRS)"), "ProjectCrs")
        )

        self.addParameter(QgsProcessingParameterFeatureSink(self.JUNCTIONS, self.tr("Junctions")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.TANKS, self.tr("Tanks")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.RESERVOIRS, self.tr("Reservoirs")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.PIPES, self.tr("Pipes")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.PUMPS, self.tr("Pumps")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.VALVES, self.tr("Valves")))

    def processAlgorithm(self, parameters, context, feedback):  # noqa N802
        if feedback is None:
            feedback = QgsProcessingFeedback()

        # PREPARE IMPORTS
        # imports are here as they are slow and only needed when processing the model.
        feedback.setProgressText("Checking dependencies")

        if environment_tools.check_dependencies():
            msg = "Missing Dependencies"
            raise QgsProcessingException(msg)

        if environment_tools.check_wntr() is None:
            feedback.setProgressText("Unpacking WNTR")
            environment_tools.install_wntr()
        try:
            import wntr
        except ImportError as e:
            raise QgsProcessingException(e) from e

        feedback.pushDebugInfo("WNTR version: " + wntr.__version__)

        feedback.setProgressText("Checking Inputs")

        source = self.parameterAsFile(parameters, self.INPUT, context)
        crs = self.parameterAsCrs(parameters, self.CRS, context)

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        feedback.setProgressText("Loading .inp file into WNTR")

        try:
            wn = wntr.network.read_inpfile(source)
            wn_gis = wntr.network.to_gis(wn)
        except ModuleNotFoundError as e:
            raise QgsProcessingException("WNTR dependencies not installed: " + str(e)) from e
        except Exception as e:
            raise QgsProcessingException("Error loading model: " + str(e)) from e

        feedback.pushInfo("WNTR model created. Model contains:")
        feedback.pushInfo(str(wn.describe(level=0)))

        feedback.setProgressText("Preparing patterns and curves")

        def _pattern_string(pn):
            return "[" + ", ".join(map(str, wn.get_pattern(pn).multipliers)) + "]" if wn.get_pattern(pn) else None

        wn_gis.junctions["base_demand"] = wn.query_node_attribute("base_demand", node_type=wntr.network.model.Junction)
        wn_gis.junctions["demand_pattern"] = wn.query_node_attribute(
            "demand_timeseries_list", node_type=wntr.network.model.Junction
        ).apply(
            lambda dtl: ("[" + ", ".join(map(str, dtl.pattern_list()[0].multipliers)) + "]")
            if dtl.pattern_list() and dtl.pattern_list()[0]
            else None
        )
        if "head_pattern_name" in wn_gis.reservoirs:
            wn_gis.reservoirs["head_pattern"] = wn_gis.reservoirs["head_pattern_name"].apply(
                lambda pn: "[" + ", ".join(map(str, wn.get_pattern(pn).multipliers)) + "]"
                if wn.get_pattern(pn)
                else None
            )
        if "vol_curve_name" in wn_gis.tanks:
            wn_gis.tanks["vol_curve"] = wn_gis.tanks["vol_curve_name"].apply(
                lambda cn: repr(wn.get_curve(cn).points) if wn.get_curve(cn) else None
            )
        # not all pumps will have a pump curve (power pumps)!
        if "pump_curve_name" in wn_gis.pumps:
            wn_gis.pumps["pump_curve"] = wn_gis.pumps["pump_curve_name"].apply(
                lambda cn: repr(wn.get_curve(cn).points)
                if cn == cn and wn.get_curve(cn)  #  noqa PLR0124 checking nan
                else None
            )
        feedback.pushInfo("Loading pump pattern")
        if "speed_pattern_name" in wn_gis.pumps:
            wn_gis.pumps["speed_pattern"] = wn_gis.pumps["speed_pattern_name"].apply(
                lambda pn: "[" + ", ".join(map(str, wn.get_pattern(pn).multipliers)) + "]"
                if wn.get_pattern(pn)
                else None
            )
        # 'energy pattern' is not called energy pattern name!
        if "energy_pattern" in wn_gis.pumps:
            wn_gis.pumps["energy_pattern"] = wn_gis.pumps["energy_pattern"].apply(
                lambda pn: "[" + ", ".join(map(str, wn.get_pattern(pn).multipliers)) + "]"
                if wn.get_pattern(pn)
                else None
            )

        feedback.setProgressText("Creating output layers")

        # first check which types of 'extra' fields to add

        allcols = []
        for element in [wn_gis.junctions, wn_gis.tanks, wn_gis.reservoirs, wn_gis.pipes, wn_gis.pumps, wn_gis.valves]:
            # Drop any column with all NaN, then add remaining columns to list
            allcols += list(element.loc[:, ~element.isna().all()].columns)

        extras = wntrqgis.fields.namesOfExtra()

        extracols = []
        for i, j in extras.items():
            if set(j) & set(allcols):
                extracols.append(i)
                feedback.pushDebugInfo("Will include columns for analysis type: " + str.lower(i))

        outputs = {}
        for layername, j in {
            "JUNCTIONS": wn_gis.junctions,
            "TANKS": wn_gis.tanks,
            "RESERVOIRS": wn_gis.reservoirs,
            "PIPES": wn_gis.pipes,
            "PUMPS": wn_gis.pumps,
            "VALVES": wn_gis.valves,
        }.items():
            geomtype = (
                QgsWkbTypes.Point if layername in ["JUNCTIONS", "TANKS", "RESERVOIRS"] else QgsWkbTypes.LineString
            )
            fields = wntrqgis.fields.getQgsFields(str.lower(layername), extracols)
            (sink, outputs[layername]) = self.parameterAsSink(parameters, layername, context, fields, geomtype, crs)

            if j.shape[0] > 0:
                j.reset_index(inplace=True, names="name")
                for jsonfeature in QgsJsonUtils.stringToFeatureList(
                    j.to_json(), QgsJsonUtils.stringToFields(j.to_json())
                ):
                    newfeature = QgsFeature()
                    newfeature.setGeometry(jsonfeature.geometry())
                    newfeature.setFields(fields)
                    for fieldname in jsonfeature.fields().names():
                        if fieldname in fields.names():
                            newfeature[fieldname] = jsonfeature[fieldname]
                    sink.addFeature(newfeature)

        feedback.setProgressText("Saving options to project file")

        QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(), "wntr_options", wn.options.to_dict())

        for layername, lyr_id in outputs.items():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(layername)
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])

        return outputs
