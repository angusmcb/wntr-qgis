from __future__ import annotations

from typing import Any

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterCrs,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSink,
)

from wntrqgis.network_parts import WqAnalysisType, WqModelLayer
from wntrqgis.wntrqgis_processing.common import LayerPostProcessor, WntrQgisProcessingBase


class TemplateLayers(QgsProcessingAlgorithm, WntrQgisProcessingBase):
    CRS = "CRS"

    def __init__(self) -> None:
        super().__init__()

        self._name = "templatelayers"
        self._display_name = "Create Template Layers"
        self._short_help_string = """
        This will create a set of 'template' layers, which you can use for building your model.
        You do not need to create or use all layers if not required for your model.
        """

    def createInstance(self):  # noqa N802
        return TemplateLayers()

    def name(self) -> str:
        return self._name

    def displayName(self) -> str:  # noqa N802
        return self.tr(self._display_name)

    def shortHelpString(self) -> str:  # noqa N802
        return self.tr(self._short_help_string)

    # def helpUrl(self) -> str:  # N802
    #    return "" # "https://www.helpsite.com"

    def initAlgorithm(self, config=None):  # noqa N802
        self.addParameter(
            QgsProcessingParameterCrs(self.CRS, self.tr("Coordinate Reference System (CRS)"), "ProjectCrs")
        )

        advanced_analysis_types = [
            (WqAnalysisType.QUALITY, "Create Fields for Water Quality Analysis"),
            (WqAnalysisType.PDA, "Create Fields for Pressure Driven Analysis"),
            (WqAnalysisType.ENERGY, "Create Fields for Energy Analysis"),
        ]
        for analysis_type, description in advanced_analysis_types:
            param = QgsProcessingParameterBoolean(
                analysis_type.name, self.tr(description), optional=True, defaultValue=False
            )
            param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(param)

        for layer in WqModelLayer:
            self.addParameter(QgsProcessingParameterFeatureSink(layer.name, self.tr(layer.friendly_name)))

    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,  # noqa ARG002
    ) -> dict:
        analysis_types_to_use = WqAnalysisType.BASE
        for analysis_type in WqAnalysisType:
            if self.parameterAsBoolean(parameters, analysis_type.name, context):
                analysis_types_to_use = analysis_types_to_use | analysis_type

        outputs: dict[str, str] = {}
        crs = self.parameterAsCrs(parameters, self.CRS, context)

        for layer in WqModelLayer:
            fields = layer.qgs_fields(analysis_types_to_use)
            wkb_type = layer.qgs_wkb_type
            (_, outputs[layer.name]) = self.parameterAsSink(parameters, layer.name, context, fields, wkb_type, crs)

        output_order = [
            WqModelLayer.JUNCTIONS,
            WqModelLayer.PIPES,
            WqModelLayer.PUMPS,
            WqModelLayer.VALVES,
            WqModelLayer.RESERVOIRS,
            WqModelLayer.TANKS,
        ]

        for layername, lyr_id in outputs.items():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(layername, True)

                layer_details = context.layerToLoadOnCompletionDetails(lyr_id)
                layer_details.setPostProcessor(self.post_processors[lyr_id])
                layer_details.groupName = self.tr("Model Layers (Template)")
                layer_details.layerSortKey = output_order.index(WqModelLayer(layername))

        return outputs
