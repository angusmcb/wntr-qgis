from __future__ import annotations

import warnings
from typing import Any

from qgis.core import (
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterCrs,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSink,
)
from qgis.PyQt.QtGui import QIcon

from wntrqgis.elements import FieldGroup, ModelField, ModelLayer
from wntrqgis.i18n import tr
from wntrqgis.interface import Writer
from wntrqgis.wntrqgis_processing.common import WntrQgisProcessingBase


class TemplateLayers(WntrQgisProcessingBase):
    CRS = "CRS"

    def __init__(self) -> None:
        super().__init__()

        self._name = "templatelayers"
        self._display_name = tr("Create Template Layers")
        self._short_help_string = tr("""
        This will create a set of 'template' layers, which you can use for building your model.
        You do not need to create or use all layers if not required for your model.
        """)

    def createInstance(self):  # noqa N802
        return TemplateLayers()

    def name(self) -> str:
        return self._name

    def displayName(self) -> str:  # noqa N802
        return tr(self._display_name)

    def shortHelpString(self) -> str:  # noqa N802
        return tr(self._short_help_string)

    def icon(self):
        return QIcon(":images/themes/default/mActionFileNew.svg")

    # def helpUrl(self) -> str:  # N802
    #    return "" # "https://www.helpsite.com"

    def initAlgorithm(self, config=None):  # noqa N802
        self.addParameter(QgsProcessingParameterCrs(self.CRS, tr("Coordinate Reference System (CRS)"), "ProjectCrs"))

        advanced_analysis_types = [
            (FieldGroup.WATER_QUALITY_ANALYSIS, tr("Create Fields for Water Quality Analysis")),
            (FieldGroup.PRESSURE_DEPENDENT_DEMAND, tr("Create Fields for Pressure Driven Analysis")),
            (FieldGroup.ENERGY, tr("Create Fields for Energy Analysis")),
        ]
        for analysis_type, description in advanced_analysis_types:
            param = QgsProcessingParameterBoolean(
                analysis_type.name, tr(description), optional=True, defaultValue=False
            )
            param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(param)

        for layer in ModelLayer:
            self.addParameter(QgsProcessingParameterFeatureSink(layer.name, layer.friendly_name))

    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict:
        super().processAlgorithm(parameters, context, feedback)

        self._ensure_wntr()

        import wntr

        analysis_types_to_use = FieldGroup.BASE
        for analysis_type in FieldGroup:
            if self.parameterAsBoolean(parameters, analysis_type.name, context):
                analysis_types_to_use = analysis_types_to_use | analysis_type

        crs = self.parameterAsCrs(parameters, self.CRS, context)

        wn = wntr.network.WaterNetworkModel()
        network_writer = Writer(wn)
        network_writer.fields = [field for field in ModelField if field.field_group & analysis_types_to_use]

        # for shapefile writing
        warnings.filterwarnings("ignore", "Field", RuntimeWarning)
        warnings.filterwarnings("ignore", "Normalized/laundered field name:", RuntimeWarning)

        outputs: dict[str, str] = {}
        layers: dict[ModelLayer, str] = {}
        for layer in ModelLayer:
            fields = network_writer.get_qgsfields(layer)
            wkb_type = layer.qgs_wkb_type
            (_, outputs[layer.name]) = self.parameterAsSink(parameters, layer.name, context, fields, wkb_type, crs)
            layers[layer] = outputs[layer.name]

        self._setup_postprocessing(layers, tr("Model Layers"), True)

        return outputs
