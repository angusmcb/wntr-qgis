from __future__ import annotations

from typing import Any, ClassVar

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterCrs,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSink,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication

import wntrqgis.fields
from wntrqgis.wntrqgis_processing.LayerPostProcessor import LayerPostProcessor


class TemplateLayers(QgsProcessingAlgorithm):
    CRS = "CRS"
    PRESSUREDEPENDENT = "PRESSUREDEPENDENT"
    QUALITY = "QUALITY"
    ENERGY = "ENERGY"
    JUNCTIONS = "JUNCTIONS"
    TANKS = "TANKS"
    RESERVOIRS = "RESERVOIRS"
    PIPES = "PIPES"
    PUMPS = "PUMPS"
    VALVES = "VALVES"

    post_processors: ClassVar[dict[str, LayerPostProcessor]] = {}

    def __init__(self) -> None:
        super().__init__()

        self._name = "templatelayers"
        self._display_name = "Create Template Layers"
        self._short_help_string = """
        This will create a set of 'template' layers, which you can use for building your model.
        You do not need to create or use all layers if not required for your model.
        Press the 'Help' button below to find out more.
        """

    def tr(self, string) -> str:
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):  # noqa N802
        return TemplateLayers()

    def name(self) -> str:
        return self._name

    def displayName(self) -> str:  # noqa N802
        return self.tr(self._display_name)

    def shortHelpString(self) -> str:  # noqa N802
        return self.tr(self._short_help_string)

    def helpUrl(self) -> str:  # noqa N802
        return "https://www.helpsite.com"

    def initAlgorithm(self, config=None):  # noqa N802
        self.addParameter(
            QgsProcessingParameterCrs(self.CRS, self.tr("Coordinate Reference System (CRS)"), "ProjectCrs")
        )

        for param_name, param_description in {
            self.QUALITY: "Create Fields for Water Quality Analysis",
            self.PRESSUREDEPENDENT: "Create Fields for Pressure-Dependent Demand Analysis",
            self.ENERGY: "Create Fields for Energy Analysis",
        }.items():
            param = QgsProcessingParameterBoolean(
                param_name, self.tr(param_description), optional=True, defaultValue=False
            )
            param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(param)

        self.addParameter(QgsProcessingParameterFeatureSink(self.JUNCTIONS, self.tr("Junctions")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.TANKS, self.tr("Tanks")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.RESERVOIRS, self.tr("Reservoirs")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.PIPES, self.tr("Pipes")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.PUMPS, self.tr("Pumps")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.VALVES, self.tr("Valves")))

    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,  # noqa ARG002
    ) -> dict:
        extracols = [
            i
            for i in [self.QUALITY, self.PRESSUREDEPENDENT, self.ENERGY]
            if self.parameterAsBoolean(parameters, i, context)
        ]

        outputs: dict[str, str] = {}
        crs = self.parameterAsCrs(parameters, self.CRS, context)
        for layername in ["JUNCTIONS", "TANKS", "RESERVOIRS", "PIPES", "PUMPS", "VALVES"]:
            geomtype = (
                QgsWkbTypes.Point if layername in ["JUNCTIONS", "TANKS", "RESERVOIRS"] else QgsWkbTypes.LineString
            )
            fields = wntrqgis.fields.getQgsFields(str.lower(layername), extracols)
            (sink, outputs[layername]) = self.parameterAsSink(parameters, layername, context, fields, geomtype, crs)

        for layername, lyr_id in outputs.items():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(layername)
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])

        return outputs
