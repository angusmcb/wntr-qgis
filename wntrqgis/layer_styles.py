from __future__ import annotations

from enum import Enum
from typing import Any

from qgis.core import (
    Qgis,
    QgsDefaultValue,
    QgsEditorWidgetSetup,
    QgsGradientColorRamp,
    QgsGraduatedSymbolRenderer,
    QgsLineSymbol,
    QgsMarkerLineSymbolLayer,
    QgsMarkerSymbol,
    QgsProperty,
    QgsSimpleLineSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsVectorLayer,
)

from wntrqgis.network_parts import WqAnalysisType, WqField, WqLayer, WqModelField, WqModelLayer, WqResultLayer


class WqFieldStyles:
    def __init__(self, field_type: WqField, layer_type: WqLayer):
        self.field_type = field_type
        self.layer_type = layer_type

    def editor_widget(self) -> QgsEditorWidgetSetup:
        # [(f.editorWidgetSetup().type(), f.editorWidgetSetup().config()) for f in iface.activeLayer().fields()]
        python_type_class = self.field_type.python_type

        if python_type_class is float:
            config: dict[str, Any] = {"Style": "SpinBox"}
            if self.field_type.analysis_type & WqAnalysisType.REQUIRED:
                config["AllowNull"] = False
            return QgsEditorWidgetSetup(
                "Range",
                config,
            )
        if python_type_class is bool:
            return QgsEditorWidgetSetup(
                "CheckBox",
                {"AllowNullState": False},
            )
        if issubclass(python_type_class, Enum):
            value_map = [{enum_instance.value: enum_instance.name} for enum_instance in python_type_class]
            return QgsEditorWidgetSetup(
                "ValueMap",
                {"map": value_map},
            )
        if python_type_class is str:
            return QgsEditorWidgetSetup("TextEdit", {"IsMultiline": False, "UseHtml": False})
        raise KeyError

    @property
    def default_value(self):
        # [f.defaultValueDefinition() for f in iface.activeLayer().fields()]
        if self.field_type is WqModelField.ROUGHNESS:
            return QgsDefaultValue("100")  # TODO: check if it is d-w or h-w
        if issubclass(self.field_type.python_type, Enum):
            return QgsDefaultValue(f"'{next(iter(self.field_type.python_type)).name}'")
        if self.field_type.python_type is str:
            return QgsDefaultValue("''")  # because 'NULL' doesn't look nice
        return QgsDefaultValue()


class WqLayerStyles:
    def __init__(self, layer_type: WqLayer):
        self.layer_type = layer_type

    def style_layer(self, layer: QgsVectorLayer):
        if isinstance(self.layer_type, WqModelLayer):
            self._style_model_layer(layer)
        if isinstance(self.layer_type, WqResultLayer):
            self._style_result_layer(layer)

    def _style_model_layer(self, layer):
        renderer = QgsSingleSymbolRenderer(self._symbol)
        layer.setRenderer(renderer)

        for i, field in enumerate(layer.fields()):
            field_styler = WqFieldStyles(WqModelField(field.name()), self.layer_type)
            layer.setEditorWidgetSetup(i, field_styler.editor_widget())
            layer.setDefaultValueDefinition(i, field_styler.default_value)

    def _style_result_layer(self, layer: QgsVectorLayer):
        if self.layer_type is WqResultLayer.NODES:
            attribute_expression = 'wntr_result_at_current_time("pressure")'
        else:
            attribute_expression = 'wntr_result_at_current_time("velocity")'
        renderer = QgsGraduatedSymbolRenderer.createRenderer(
            layer,
            attribute_expression,
            8,
            QgsGraduatedSymbolRenderer.Mode.Quantile,
            self._symbol,
            QgsGradientColorRamp.create(SPECTRAL_RAMP),
        )
        layer.setRenderer(renderer)

        temporal_properties = layer.temporalProperties()
        temporal_properties.setIsActive(True)
        temporal_properties.setMode(Qgis.VectorTemporalMode.ModeRedrawLayerOnly)

    @property
    def _symbol(self):
        if self.layer_type is WqModelLayer.JUNCTIONS:
            return QgsMarkerSymbol.createSimple(CIRCLE | WHITE_FILL | HAIRLINE_STROKE | JUNCTION_SIZE)

        if self.layer_type is WqModelLayer.TANKS:
            return QgsMarkerSymbol.createSimple(SQUARE | WHITE_FILL | HAIRLINE_STROKE | TANK_SIZE)

        if self.layer_type is WqModelLayer.RESERVOIRS:
            return QgsMarkerSymbol.createSimple(TRAPEZOID | WHITE_FILL | HAIRLINE_STROKE | RESERVOIR_SIZE)

        if self.layer_type is WqModelLayer.PIPES:
            return QgsLineSymbol.createSimple(HAIRWIDTH_LINE | TRIM_ENDS)

        background_line = QgsSimpleLineSymbolLayer.create(HAIRWIDTH_LINE | GREY_LINE | DOTTY_LINE)

        if self.layer_type is WqModelLayer.VALVES:
            left_triangle = QgsSimpleMarkerSymbolLayer.create(TRIANGLE | BLACK_FILL | NO_STROKE)
            right_triangle = QgsSimpleMarkerSymbolLayer.create(TRIANGLE | BLACK_FILL | NO_STROKE | ROTATE_180)
            valve_marker = QgsMarkerSymbol([left_triangle, right_triangle])
            return self._line_with_marker(background_line, valve_marker)

        if self.layer_type is WqModelLayer.PUMPS:
            pump_body = QgsSimpleMarkerSymbolLayer.create(CIRCLE | PUMP_SIZE | BLACK_FILL | NO_STROKE)
            pump_outlet = QgsSimpleMarkerSymbolLayer.create(OUTLET_SQUARE | PUMP_SIZE | BLACK_FILL | NO_STROKE)
            pump_marker = QgsMarkerSymbol([pump_body, pump_outlet])
            return self._line_with_marker(background_line, pump_marker)

        if self.layer_type is WqResultLayer.NODES:
            return QgsMarkerSymbol.createSimple(CIRCLE | NO_STROKE | NODE_SIZE)

        if self.layer_type is WqResultLayer.LINKS:
            line = QgsSimpleLineSymbolLayer.create(THICK_LINE | TRIM_ENDS)
            arrow = QgsMarkerSymbol.createSimple(ARROW | THICK_STROKE)
            exp = QgsProperty.fromExpression("if(wntr_result_at_current_time( flowrate ) <0,180,0)")
            arrow.setDataDefinedAngle(exp)
            return self._line_with_marker(line, arrow)

        raise KeyError

    def _line_with_marker(self, background_line, marker):
        marker_line = QgsMarkerLineSymbolLayer.create(CENTRAL_PLACEMENT)
        marker_line.setSubSymbol(marker)
        return QgsLineSymbol([background_line, marker_line])


# USE THE FOLLOWING TO DISCOVER WHAT PROPERTIES ARE AVAILABLE:
# iface.activeLayer().renderer().symbol().symbolLayers()[0].properties()
# iface.activeLayer().renderer().symbol().symbolLayers()[0].subSymbol().symbolLayers()[0].properties()

CIRCLE = {"name": "circle"}
SQUARE = {"name": "square", "joinstyle": "miter"}
TRAPEZOID = {"name": "trapezoid", "angle": "180", "joinstyle": "miter"}
TRIANGLE = {"name": "filled_arrowhead"}
ARROW = {"name": "arrowhead", "offset": "0.5,0"}
OUTLET_SQUARE = {"name": "half_square", "vertical_anchor_point": "2", "angle": "90"}
WHITE_FILL = {"color": "white"}
BLACK_FILL = {"color": "black"}
HAIRLINE_STROKE = {"outline_color": "black", "outline_style": "solid", "outline_width": "0"}
THICK_STROKE = {"outline_width": "0.4"}
NO_STROKE = {"outline_style": "no"}
JUNCTION_SIZE = {"size": "1.8"}
NODE_SIZE = {"size": "2.0"}
TANK_SIZE = {"size": "2.5"}
RESERVOIR_SIZE = {"size": "5"}
VALVE_SIZE = {"size": "3"}
PUMP_SIZE = {"size": "2"}
HAIRWIDTH_LINE = {"line_width": "0"}
THICK_LINE = {"line_width": "0.4"}
TRIM_ENDS = {"trim_distance_end": "0.9", "trim_distance_start": "0.9"}
DOTTY_LINE = {"line_style": "dot"}
GREY_LINE = {"line_color": "35,35,35,255,rgb:0.13725490196078433,0.13725490196078433,0.13725490196078433,1"}
ROTATE_180 = {"angle": "180"}
CENTRAL_PLACEMENT = {"placements": "CentralPoint"}


# iface.activeLayer().renderer().sourceColorRamp().properties()
SPECTRAL_RAMP = {
    "color1": "43,131,186,255,rgb:0.16862745098039217,0.51372549019607838,0.72941176470588232,1",
    "color2": "215,25,28,255,rgb:0.84313725490196079,0.09803921568627451,0.10980392156862745,1",
    "direction": "cw",
    "discrete": "0",
    "rampType": "gradient",
    "spec": "rgb",
    "stops": "0.25;171,221,164,255,rgb:0.6705882352941176,0.8666666666666667,0.64313725490196083,1;rgb;cw:0.5;255,255,191,255,rgb:1,1,0.74901960784313726,1;rgb;cw:0.75;253,174,97,255,rgb:0.99215686274509807,0.68235294117647061,0.38039215686274508,1;rgb;cw",
}
