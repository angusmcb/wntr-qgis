from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from qgis.core import (
    Qgis,
    QgsAbstractVectorLayerLabeling,
    QgsClassificationQuantile,
    QgsDefaultValue,
    QgsEditorWidgetSetup,
    QgsFeatureRenderer,
    QgsField,
    QgsGraduatedSymbolRenderer,
    QgsLineSymbol,
    QgsMarkerLineSymbolLayer,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsProperty,
    QgsSimpleLineSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsStyle,
    QgsSymbol,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
    QgsVectorLayerTemporalProperties,
)

from wntrqgis.elements import (
    CurveType,
    Field,
    FieldGroup,
    InitialStatus,
    ModelLayer,
    PatternType,
    ResultLayer,
    _AbstractValueMap,
)


def style(layer: QgsVectorLayer, layer_type: ModelLayer | ResultLayer, theme: Literal["extended"] | None = None):
    styler = _LayerStyler(layer, layer_type, theme)

    layer.setRenderer(styler.layer_renderer)
    layer.setLabeling(styler.labeling)
    styler.setup_extended_period()

    _setup_fields(layer, layer_type)


def _setup_fields(layer: QgsVectorLayer, layer_type: ModelLayer | ResultLayer):
    field: QgsField
    for i, field in enumerate(layer.fields()):
        try:
            field_styler = _FieldStyler(Field(field.name().lower()), layer_type)
        except ValueError:
            continue
        layer.setEditorWidgetSetup(i, field_styler.editor_widget)
        layer.setDefaultValueDefinition(i, field_styler.default_value)
        layer.setFieldAlias(i, field_styler.alias)
        layer.setConstraintExpression(i, *field_styler.constraint)


class _FieldStyler:
    def __init__(self, field_type: Field, layer_type: ModelLayer | ResultLayer):
        self.field_type = field_type
        self.layer_type = layer_type

    @property
    def editor_widget(self) -> QgsEditorWidgetSetup:
        # [(f.editorWidgetSetup().type(), f.editorWidgetSetup().config()) for f in iface.activeLayer().fields()]
        python_type_class = self.field_type.python_type

        if python_type_class is float:
            config: dict[str, Any] = {"Style": "SpinBox", "Precision": 2}
            if self.field_type.field_group & FieldGroup.REQUIRED:
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
        if issubclass(python_type_class, _AbstractValueMap):
            enum_list = list(python_type_class)
            if python_type_class is InitialStatus and self.layer_type in [ModelLayer.PIPES, ModelLayer.PUMPS]:
                enum_list = [InitialStatus.OPEN, InitialStatus.CLOSED]

            value_map = [{enum_instance.friendly_name: enum_instance.name} for enum_instance in enum_list]

            return QgsEditorWidgetSetup(
                "ValueMap",
                {"map": value_map},
            )
        if issubclass(python_type_class, str):
            return QgsEditorWidgetSetup("TextEdit", {"IsMultiline": False, "UseHtml": False})
        raise KeyError  # pragma: no cover

    @property
    def default_value(self) -> QgsDefaultValue:
        # [f.defaultValueDefinition() for f in iface.activeLayer().fields()]

        if self.field_type is Field.ROUGHNESS:
            return QgsDefaultValue("100")  # TODO: check if it is d-w or h-w

        if self.field_type is Field.DIAMETER and (
            self.layer_type is ModelLayer.PIPES or self.layer_type is ModelLayer.VALVES
        ):
            return QgsDefaultValue("100")  # TODO: check if it is lps or gpm...

        if self.field_type in [Field.MINOR_LOSS]:
            return QgsDefaultValue("0.0")

        if self.field_type is Field.BASE_SPEED:
            return QgsDefaultValue("1.0")

        if self.field_type is Field.POWER:
            return QgsDefaultValue("50.0")

        if self.field_type.python_type is InitialStatus and self.layer_type is ModelLayer.VALVES:
            return QgsDefaultValue(f"'{InitialStatus.ACTIVE.name}'")

        if self.field_type.python_type is InitialStatus and self.layer_type in [ModelLayer.PUMPS, ModelLayer.PIPES]:
            return QgsDefaultValue(f"'{InitialStatus.OPEN.name}'")

        if issubclass(self.field_type.python_type, Enum):
            return QgsDefaultValue(f"'{next(iter(self.field_type.python_type)).name}'")

        if self.field_type.python_type in [str, CurveType, PatternType]:
            return QgsDefaultValue("''")  # because 'NULL' doesn't look nice

        return QgsDefaultValue()

    @property
    def alias(self) -> str:
        return self.field_type.friendly_name

    @property
    def constraint(self) -> tuple[str, str] | tuple[None, None]:
        """Returns field constraint. Either:
        tuple of constraint expression and description for the field
        None, None if no constraint is needed.
        """

        if self.field_type is Field.NAME:
            return (
                "name IS NULL OR (length(name) < 32 AND name NOT LIKE '% %')",
                "Name must either be blank for automatic naming, or a string of up to 31 characters with no spaces",
            )
        if self.field_type is Field.DIAMETER and self.layer_type in [ModelLayer.PIPES, ModelLayer.VALVES]:
            return "diameter > 0", "Diameter must be greater than 0"
        if self.field_type is Field.ROUGHNESS:
            return "roughness > 0", "Roughness must be greater than 0"
        if self.field_type is Field.LENGTH:
            return "length is NULL  OR  length > 0", "Length must be empty/NULL (will be calculated) or greater than 0"

        if self.field_type is Field.MINOR_LOSS and self.layer_type in [ModelLayer.PIPES, ModelLayer.VALVES]:
            return "minor_loss >= 0", "Minor loss must be greater than or equal to 0"
        if self.field_type is Field.BASE_SPEED and self.layer_type is ModelLayer.PUMPS:
            return "base_speed > 0", "Base speed must be greater than 0"
        return None, None


class _LayerStyler:
    def __init__(self, layer: QgsVectorLayer, layer_type: ModelLayer | ResultLayer, theme: str | None = None):
        self.layer = layer
        self.layer_type = layer_type
        self.theme = theme

    def setup_extended_period(self) -> None:
        if isinstance(self.layer_type, ResultLayer) and self.theme == "extended":
            temporal_properties: QgsVectorLayerTemporalProperties = self.layer.temporalProperties()
            temporal_properties.setIsActive(True)
            temporal_properties.setMode(Qgis.VectorTemporalMode.RedrawLayerOnly)

    @property
    def labeling(self) -> QgsAbstractVectorLayerLabeling | None:
        if self.layer_type is ResultLayer.LINKS:
            label_settings = QgsPalLayerSettings()
            label_settings.drawLabels = False
            label_settings.fieldName = "flowrate"
            label_settings.decimals = 1
            label_settings.formatNumbers = True
            return QgsVectorLayerSimpleLabeling(label_settings)

        return None

    @property
    def layer_renderer(self) -> QgsFeatureRenderer:
        if isinstance(self.layer_type, ModelLayer):
            return QgsSingleSymbolRenderer(self._symbol)

        if self.layer_type is ResultLayer.NODES:
            attribute_expression = 'wntr_result_at_current_time("pressure")' if self.theme == "extended" else "pressure"
        else:
            attribute_expression = 'wntr_result_at_current_time("velocity")' if self.theme == "extended" else "velocity"

        renderer = QgsGraduatedSymbolRenderer()
        renderer.setClassAttribute(attribute_expression)
        renderer.setSourceSymbol(self._symbol)
        classification_method = QgsClassificationQuantile()
        classification_method.setLabelPrecision(1)
        classification_method.setLabelTrimTrailingZeroes(False)
        renderer.setClassificationMethod(classification_method)

        renderer.updateClasses(self.layer, 5)

        color_ramp = QgsStyle().defaultStyle().colorRamp("Spectral")
        color_ramp.invert()
        renderer.updateColorRamp(color_ramp)

        return renderer

    @property
    def _symbol(self) -> QgsSymbol:
        if self.layer_type is ModelLayer.JUNCTIONS:
            return QgsMarkerSymbol.createSimple(CIRCLE | WHITE_FILL | HAIRLINE_STROKE | JUNCTION_SIZE)

        if self.layer_type is ModelLayer.TANKS:
            return QgsMarkerSymbol.createSimple(SQUARE | WHITE_FILL | HAIRLINE_STROKE | TANK_SIZE)

        if self.layer_type is ModelLayer.RESERVOIRS:
            return QgsMarkerSymbol.createSimple(TRAPEZOID | WHITE_FILL | HAIRLINE_STROKE | RESERVOIR_SIZE)

        if self.layer_type is ModelLayer.PIPES:
            return QgsLineSymbol.createSimple(MEDIUM_LINE | TRIM_ENDS)

        background_line = QgsSimpleLineSymbolLayer.create(HAIRWIDTH_LINE | GREY_LINE | DOTTY_LINE)

        if self.layer_type is ModelLayer.VALVES:
            left_triangle = QgsSimpleMarkerSymbolLayer.create(TRIANGLE | BLACK_FILL | NO_STROKE)
            right_triangle = QgsSimpleMarkerSymbolLayer.create(TRIANGLE | BLACK_FILL | NO_STROKE | ROTATE_180)
            # creating using nomral __init__ with list crashes 3.34
            valve_marker = QgsMarkerSymbol.createSimple(left_triangle.properties())  # left_triangle, right_triangle])
            valve_marker.appendSymbolLayer(right_triangle)
            return _line_with_marker(background_line, valve_marker)

        if self.layer_type is ModelLayer.PUMPS:
            pump_body = QgsSimpleMarkerSymbolLayer.create(CIRCLE | PUMP_SIZE | BLACK_FILL | NO_STROKE)
            pump_outlet = QgsSimpleMarkerSymbolLayer.create(OUTLET_SQUARE | PUMP_SIZE | BLACK_FILL | NO_STROKE)
            pump_marker = QgsMarkerSymbol.createSimple(pump_body.properties())
            pump_marker.appendSymbolLayer(pump_outlet)
            return _line_with_marker(background_line, pump_marker)

        if self.layer_type is ResultLayer.NODES:
            return QgsMarkerSymbol.createSimple(CIRCLE | NO_STROKE | NODE_SIZE)

        if self.layer_type is ResultLayer.LINKS:
            line = QgsSimpleLineSymbolLayer.create(THICK_LINE)
            arrow = QgsMarkerSymbol.createSimple(ARROW | THICK_STROKE)

            flowrate_field = "wntr_result_at_current_time( flowrate )" if self.theme == "extended" else "flowrate"

            exp = QgsProperty.fromExpression(f"if( {flowrate_field} <0,180,0)")
            arrow.setDataDefinedAngle(exp)
            return _line_with_marker(line, arrow)

        raise KeyError  # pragma: no cover


def _line_with_marker(background_line: QgsLineSymbol, marker: QgsMarkerSymbol) -> QgsLineSymbol:
    marker_line = QgsMarkerLineSymbolLayer.create(CENTRAL_PLACEMENT)
    marker_line.setSubSymbol(marker)
    combined_symbol = QgsLineSymbol.createSimple(background_line.properties())
    combined_symbol.appendSymbolLayer(marker_line)
    return combined_symbol


# USE THE FOLLOWING TO DISCOVER WHAT PROPERTIES ARE AVAILABLE:
# iface.activeLayer().renderer().symbol().symbolLayers()[0].properties()
# iface.activeLayer().renderer().symbol().symbolLayers()[0].subSymbol().symbolLayers()[0].properties()

CIRCLE = {"name": "circle"}
SQUARE = {"name": "square", "joinstyle": "miter"}
TRAPEZOID = {"name": "trapezoid", "angle": "180", "joinstyle": "miter"}
TRIANGLE = {"name": "filled_arrowhead"}
ARROW = {"name": "arrowhead", "offset": "0.5,0", "size": "2.0"}
OUTLET_SQUARE = {"name": "half_square", "vertical_anchor_point": "2", "angle": "90"}
WHITE_FILL = {"color": "white"}
BLACK_FILL = {"color": "black"}
HAIRLINE_STROKE = {"outline_color": "black", "outline_style": "solid", "outline_width": "0"}
THICK_STROKE = {"outline_width": "0.6"}
NO_STROKE = {"outline_style": "no"}
JUNCTION_SIZE = {"size": "1.8"}
NODE_SIZE = {"size": "2.0"}
TANK_SIZE = {"size": "2.5"}
RESERVOIR_SIZE = {"size": "5"}
VALVE_SIZE = {"size": "3"}
PUMP_SIZE = {"size": "2"}
HAIRWIDTH_LINE = {"line_width": "0"}
MEDIUM_LINE = {"line_width": "0.4"}
THICK_LINE = {"line_width": "0.6"}
TRIM_ENDS = {"trim_distance_end": "0.9", "trim_distance_start": "0.9"}
DOTTY_LINE = {"line_style": "dot"}
GREY_LINE = {"line_color": "35,35,35,255,rgb:0.13725490196078433,0.13725490196078433,0.13725490196078433,1"}
ROTATE_180 = {"angle": "180"}
CENTRAL_PLACEMENT = {"placements": "CentralPoint"}
