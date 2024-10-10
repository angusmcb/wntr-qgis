from __future__ import annotations  # noqa

from pathlib import Path

from qgis.core import (
    QgsExpressionContextUtils,
    QgsProcessingLayerPostProcessorInterface,
    QgsProject,
    QgsVectorLayer,
)


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
