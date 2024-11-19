from qgis.core import (
    QgsLineSymbol,
    QgsMarkerLineSymbolLayer,
    QgsMarkerSymbol,
    QgsSimpleLineSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
)

from wntrqgis.network_parts import WqLayer, WqModelLayer, WqResultLayer


class WqLayerStyles:
    def __init__(self, layer_type: WqLayer):
        self.layer_type = layer_type

    @property
    def symbol(self):
        if self.layer_type is WqModelLayer.JUNCTIONS:
            return QgsMarkerSymbol.createSimple(CIRCLE | WHITE_FILL | HAIRLINE_STROKE | JUNCTION_SIZE)

        if self.layer_type is WqModelLayer.TANKS:
            return QgsMarkerSymbol.createSimple(SQUARE | WHITE_FILL | HAIRLINE_STROKE | TANK_SIZE)

        if self.layer_type is WqModelLayer.RESERVOIRS:
            return QgsMarkerSymbol.createSimple(TRAPEZOID | WHITE_FILL | HAIRLINE_STROKE | RESERVOIR_SIZE)

        if self.layer_type is WqModelLayer.PIPES:
            return QgsLineSymbol.createSimple(HAIRWIDTH_LINE | TRIM_ENDS)

        if self.layer_type is WqModelLayer.VALVES:
            left_triangle = QgsSimpleMarkerSymbolLayer.create(ARROWHEAD | BLACK_FILL | NO_STROKE)
            right_triangle = QgsSimpleMarkerSymbolLayer.create(ARROWHEAD | BLACK_FILL | NO_STROKE | ROTATE_180)
            valve_marker = QgsMarkerSymbol([left_triangle, right_triangle])
            return self._line_with_marker(valve_marker)

        if self.layer_type is WqModelLayer.PUMPS:
            pump_body = QgsSimpleMarkerSymbolLayer.create(CIRCLE | PUMP_SIZE | BLACK_FILL | NO_STROKE)
            pump_outlet = QgsSimpleMarkerSymbolLayer.create(OUTLET_SQUARE | PUMP_SIZE | BLACK_FILL | NO_STROKE)
            pump_marker = QgsMarkerSymbol([pump_body, pump_outlet])
            return self._line_with_marker(pump_marker)

        raise KeyError

    def _line_with_marker(self, marker):
        background_line = QgsSimpleLineSymbolLayer.create(HAIRWIDTH_LINE | GREY_LINE | DOTTY_LINE)
        marker_line = QgsMarkerLineSymbolLayer.create(CENTRAL_PLACEMENT)
        marker_line.setSubSymbol(marker)
        return QgsLineSymbol([background_line, marker_line])


# USE THE FOLLOWING TO DISCOVER WHAT PROPERTIES ARE AVAILABLE:
# iface.activeLayer().renderer().symbol().symbolLayers()[0].properties()
# iface.activeLayer().renderer().symbol().symbolLayers()[0].subSymbol().symbolLayers()[0].properties()

CIRCLE = {"name": "circle"}
SQUARE = {"name": "square", "joinstyle": "miter"}
TRAPEZOID = {"name": "trapezoid", "angle": "180", "joinstyle": "miter"}
ARROWHEAD = {"name": "filled_arrowhead"}
OUTLET_SQUARE = {"name": "half_square", "vertical_anchor_point": "2", "angle": "90"}
WHITE_FILL = {"color": "white"}
BLACK_FILL = {"color": "black"}
HAIRLINE_STROKE = {"outline_color": "black", "outline_style": "solid", "outline_width": "0"}
NO_STROKE = {"outline_style": "no"}
JUNCTION_SIZE = {"size": "1.8"}
TANK_SIZE = {"size": "2.5"}
RESERVOIR_SIZE = {"size": "5"}
VALVE_SIZE = {"size": "3"}
PUMP_SIZE = {"size": "2"}
HAIRWIDTH_LINE = {"line_style": "solid", "line_width": "0"}
TRIM_ENDS = {"trim_distance_end": "0.9", "trim_distance_start": "0.9"}
DOTTY_LINE = {"line_style": "dot"}
GREY_LINE = {"line_color": "35,35,35,255,rgb:0.13725490196078433,0.13725490196078433,0.13725490196078433,1"}
ROTATE_180 = {"angle": "180"}
CENTRAL_PLACEMENT = {"placements": "CentralPoint"}
