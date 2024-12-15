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

from wntrqgis.network_parts import FieldGroup, ModelLayer
from wntrqgis.resource_manager import WqIcon
from wntrqgis.wntrqgis_processing.common import WntrQgisProcessingBase


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

    def icon(self):
        return WqIcon.NEW.q_icon

    # def helpUrl(self) -> str:  # N802
    #    return "" # "https://www.helpsite.com"

    def initAlgorithm(self, config=None):  # noqa N802
        self.addParameter(
            QgsProcessingParameterCrs(self.CRS, self.tr("Coordinate Reference System (CRS)"), "ProjectCrs")
        )

        advanced_analysis_types = [
            (FieldGroup.WATER_QUALITY_ANALYSIS, "Create Fields for Water Quality Analysis"),
            (FieldGroup.PRESSURE_DEPENDENT_DEMAND, "Create Fields for Pressure Driven Analysis"),
            (FieldGroup.ENERGY, "Create Fields for Energy Analysis"),
        ]
        for analysis_type, description in advanced_analysis_types:
            param = QgsProcessingParameterBoolean(
                analysis_type.name, self.tr(description), optional=True, defaultValue=False
            )
            param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(param)

        for layer in ModelLayer:
            self.addParameter(QgsProcessingParameterFeatureSink(layer.name, self.tr(layer.friendly_name)))

    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict:
        WntrQgisProcessingBase.processAlgorithm(self, parameters, context, feedback)

        analysis_types_to_use = FieldGroup.BASE
        for analysis_type in FieldGroup:
            if self.parameterAsBoolean(parameters, analysis_type.name, context):
                analysis_types_to_use = analysis_types_to_use | analysis_type

        outputs: dict[str, str] = {}
        crs = self.parameterAsCrs(parameters, self.CRS, context)

        for layer in ModelLayer:
            fields = layer.qgs_fields(analysis_types_to_use)
            wkb_type = layer.qgs_wkb_type
            (_, outputs[layer]) = self.parameterAsSink(parameters, layer.name, context, fields, wkb_type, crs)

        self._setup_postprocessing(outputs, "Model Layers", True)

        return outputs
