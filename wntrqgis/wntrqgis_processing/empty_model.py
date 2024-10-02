from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.core import (
    QgsExpressionContextUtils,
    QgsField,
    QgsFields,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication, QVariant

import wntrqgis.fields

class EmptyLayers(QgsProcessingAlgorithm):
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

    post_processors = dict()

    def __init__(self) -> None:
        super().__init__()

        self._name = "emptymodel"
        self._display_name = "Create Empty Layers"
        self._group_id = ""
        self._group = ""
        self._short_help_string = ""

    def tr(self, string) -> str:
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):  # noqa N802
        return EmptyLayers()

    def name(self) -> str:
        return self._name

    def displayName(self) -> str:  # noqa N802
        return self.tr(self._display_name)

    def groupId(self) -> str:  # noqa N802
        return self._group_id

    def group(self) -> str:
        return self.tr(self._group)

    def shortHelpString(self) -> str:  # noqa N802
        return self.tr(self._short_help_string)

    def initAlgorithm(self, config=None):  # noqa N802
        self.addParameter(QgsProcessingParameterCrs(self.CRS, "CRS", 'ProjectCrs'))

        param = QgsProcessingParameterBoolean(self.QUALITY, 'Create Fields for Water Quality Analysis', optional=True, defaultValue=False)
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterBoolean(self.PRESSUREDEPENDENT, 'Create Fields for Pressure-Dependent Demand Analysis', optional=True, defaultValue=False)
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterBoolean(self.ENERGY, 'Create Fields for Energy Analysis', optional=True, defaultValue=False)
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
        feedback: QgsProcessingFeedback,
    ) -> dict:
        """
        Here is where the processing itself takes place.
        """

        # Initialize feedback if it is None
        if feedback is None:
            feedback = QgsProcessingFeedback()




        outputs = {
            "junctions": {"parameter": self.JUNCTIONS, "type": QgsWkbTypes.Point},
            "tanks": {"parameter": self.TANKS, "type": QgsWkbTypes.Point},
            "reservoirs": {"parameter": self.RESERVOIRS, "type": QgsWkbTypes.Point},
            "pipes": {"parameter": self.PIPES, "type": QgsWkbTypes.LineString},
            "pumps": {"parameter": self.PUMPS, "type": QgsWkbTypes.LineString},
            "valves": {"parameter": self.VALVES, "type": QgsWkbTypes.LineString},
        }



        extra = [i for i in [self.QUALITY,self.PRESSUREDEPENDENT,self.ENERGY] if self.parameterAsBoolean(parameters, i, context)]

        returnoutputs = dict()
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

    def postProcessLayer(self, layer, context, feedback):
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
