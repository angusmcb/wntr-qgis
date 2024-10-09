from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from qgis.core import (
    QgsExpressionContextUtils,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterCrs,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSink,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication

import wntrqgis.fields


class EmptyLayers(QgsProcessingAlgorithm):
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

        self._name = "emptymodel"
        self._display_name = "Create Empty Layers"
        self._group_id = ""
        self._group = ""
        self._short_help_string = ""

    def tr(self, string) -> str:
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):  # noqa N802
        return EmptyLayers()

    def name(self) -> str:
        return self._name

    def displayName(self) -> str:  # noqa N802
        return self.tr(self._display_name)

    def shortHelpString(self) -> str:  # noqa N802
        return self.tr(self._short_help_string)

    def initAlgorithm(self, config=None):  # noqa N802
        self.addParameter(QgsProcessingParameterCrs(self.CRS, "CRS", "ProjectCrs"))

        param = QgsProcessingParameterBoolean(
            self.QUALITY, "Create Fields for Water Quality Analysis", optional=True, defaultValue=False
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterBoolean(
            self.PRESSUREDEPENDENT,
            "Create Fields for Pressure-Dependent Demand Analysis",
            optional=True,
            defaultValue=False,
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterBoolean(
            self.ENERGY, "Create Fields for Energy Analysis", optional=True, defaultValue=False
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
        outputs = {
            "junctions": {"parameter": self.JUNCTIONS, "type": QgsWkbTypes.Point},
            "tanks": {"parameter": self.TANKS, "type": QgsWkbTypes.Point},
            "reservoirs": {"parameter": self.RESERVOIRS, "type": QgsWkbTypes.Point},
            "pipes": {"parameter": self.PIPES, "type": QgsWkbTypes.LineString},
            "pumps": {"parameter": self.PUMPS, "type": QgsWkbTypes.LineString},
            "valves": {"parameter": self.VALVES, "type": QgsWkbTypes.LineString},
        }

        extra = [
            i
            for i in [self.QUALITY, self.PRESSUREDEPENDENT, self.ENERGY]
            if self.parameterAsBoolean(parameters, i, context)
        ]

        returnoutputs = {}
        for i in outputs:
            fields = wntrqgis.fields.getQgsFields(i, extra)

            (outputs[i]["sink"], dest_id) = self.parameterAsSink(
                parameters,
                outputs[i]["parameter"],
                context,
                fields,
                outputs[i]["type"],
                self.parameterAsCrs(parameters, self.CRS, context),
            )
            returnoutputs[outputs[i]["parameter"]] = dest_id

            if context.willLoadLayerOnCompletion(dest_id):
                self.post_processors[dest_id] = LayerPostProcessor.create(outputs[i]["parameter"])
                context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(self.post_processors[dest_id])

        """
        for lyr_id in returnoutputs.values():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create()
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])
        """
        return returnoutputs


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None
    layertype = None

    def postProcessLayer(self, layer, context, feedback):  # noqa N802 ARG002
        if not isinstance(layer, QgsVectorLayer):
            return
        layer.loadNamedStyle(str(Path(__file__).parent.parent / "resources" / "styles" / (self.layertype + ".qml")))
        wntr_layers = QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable("wntr_layers")
        if wntr_layers is None:
            wntr_layers = {}
        wntr_layers[self.layertype] = layer.id()
        QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(), "wntr_layers", wntr_layers)

    @staticmethod
    def create(layertype) -> LayerPostProcessor:
        LayerPostProcessor.instance = LayerPostProcessor()
        LayerPostProcessor.instance.layertype = layertype
        return LayerPostProcessor.instance
