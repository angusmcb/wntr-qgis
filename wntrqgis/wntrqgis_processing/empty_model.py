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

from wntrqgis.utilswithoutwntr import WqAnalysisType, WqInLayer
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

        for analysis_type in WqAnalysisType:
            match analysis_type:
                case WqAnalysisType.BASE:
                    continue
                case WqAnalysisType.QUALITY:
                    description = "Create Fields for Water Quality Analysis"
                case WqAnalysisType.PDA:
                    description = "Create Fields for Pressure Driven Analysis"
                case WqAnalysisType.ENERGY:
                    description = "Create Fields for Energy Analysis"

            param = QgsProcessingParameterBoolean(
                analysis_type.name, self.tr(description), optional=True, defaultValue=False
            )
            param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(param)

        for layer in WqInLayer:
            self.addParameter(QgsProcessingParameterFeatureSink(layer.name, self.tr(layer.friendly_name)))

    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,  # noqa ARG002
    ) -> dict:
        analysis_types_to_use = WqAnalysisType.BASE

        for analysis_type in WqAnalysisType:
            if analysis_type is WqAnalysisType.BASE:
                continue
            if self.parameterAsBoolean(parameters, analysis_type.name, context):
                analysis_types_to_use = analysis_types_to_use | analysis_type

        outputs: dict[str, str] = {}
        crs = self.parameterAsCrs(parameters, self.CRS, context)

        for layer in WqInLayer:
            fields = layer.qgs_fields(analysis_types_to_use)
            wkb_type = layer.qgs_wkb_type
            (sink, outputs[layer.name]) = self.parameterAsSink(parameters, layer.name, context, fields, wkb_type, crs)

        ### add virtual fields
        # for layername in linklayers:
        #    lyr = QgsProcessingUtils.mapLayerFromString(outputs[layername], context)
        #    lyr.addExpressionField(**wntrqgis.fields.linked_node_field("start"))
        #    lyr.addExpressionField(**wntrqgis.fields.linked_node_field("end"))

        for layername, lyr_id in outputs.items():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(layername)
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])

        return outputs
