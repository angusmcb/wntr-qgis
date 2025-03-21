from __future__ import annotations

import pytest
import wntr
from qgis.core import QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer

import wntrqgis


def layer(layer_type: str, fields: list[tuple[str, type]] = [], crs: str | None = None) -> QgsVectorLayer:
    field_string = "&".join([f"field={name}:{type_to_string(the_type)}" for name, the_type in fields])
    crs_string = f"&crs={crs}" if crs else ""
    return QgsVectorLayer(f"{layer_type}?{field_string}{crs_string}", "", "memory")


def type_to_string(the_type: type) -> str:
    if the_type is str:
        return "string"
    if the_type is float:
        return "double"
    if the_type is int:
        return "integer"
    if the_type is bool:
        return "boolean"
    msg = f"Unsupported type: {the_type}"
    raise ValueError(msg)


def add_point(layer: QgsVectorLayer, point: tuple[float, float], fields: list = []):
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*point)))
    feature.setAttributes(fields)
    layer.dataProvider().addFeature(feature)
    layer.updateExtents()


def add_line(layer: QgsVectorLayer, points: list[tuple[float, float]], fields: list = []):
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in points]))
    feature.setAttributes(fields)
    layer.dataProvider().addFeature(feature)
    layer.updateExtents()


@pytest.fixture
def simple_layers():
    junction_layer = layer("point", [("name", str), ("base_demand", float), ("length", float)])
    add_point(junction_layer, (1, 1), ["J1", 1])
    tank_layer = layer("point", [("name", str)])
    add_point(tank_layer, (4, 5), ["T1"])
    pipe_layer = layer("linestring", [("name", str), ("roughness", float)])
    add_line(pipe_layer, [(1, 1), (4, 5)], ["P1", 100])
    return {"JUNCTIONS": junction_layer, "PIPES": pipe_layer, "TANKS": tank_layer}


def test_simple_layers(simple_layers):
    wn = wntrqgis.from_qgis(simple_layers, "LPS", "H-W")
    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert "J1" in wn.junction_name_list


def test_broken_layername(simple_layers):
    simple_layers["wrongname"] = simple_layers["JUNCTIONS"]

    with pytest.raises(ValueError, match="'wrongname' is not a valid layer type."):
        wntrqgis.from_qgis(simple_layers, "LPS", "H-W")


def test_minimum_attributes():
    junction_layer = layer("Point", [])
    add_point(junction_layer, (1, 1))
    add_point(junction_layer, (2, 2))

    tank_layer = layer("Point", [])
    add_point(tank_layer, (3, 3))

    reservoir_layer = layer("Point", [])
    add_point(reservoir_layer, (4, 4))

    pipe_layer = layer("LineString", [])
    add_line(pipe_layer, [(1, 1), (4, 4)])

    pump_layer = layer("LineString", [("pump_type", str), ("power", float)])
    add_line(pump_layer, [(2, 2), (3, 3)], ["power", 10])

    valve_layer = layer("LineString", [("valve_type", str)])
    add_line(valve_layer, [(1, 1), (2, 2)], ["PRV"])

    layers = {
        "JUNCTIONS": junction_layer,
        "TANKS": tank_layer,
        "RESERVOIRS": reservoir_layer,
        "PIPES": pipe_layer,
        "PUMPS": pump_layer,
        "VALVES": valve_layer,
    }

    wn = wntrqgis.from_qgis(layers, "LPS", "H-W")

    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert "1" in wn.junction_name_list
    assert "2" in wn.junction_name_list
    assert "4" in wn.tank_name_list
    assert "3" in wn.reservoir_name_list
    assert "1" in wn.pipe_name_list
    assert "2" in wn.pump_name_list
    assert "3" in wn.valve_name_list


@pytest.mark.parametrize("headloss", ["H-W", "D-W", "C-M"])
def test_from_qgis_headloss(simple_layers, headloss):
    wn = wntrqgis.from_qgis(simple_layers, "LPS", headloss=headloss)
    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert "J1" in wn.junction_name_list
    assert "T1" in wn.tank_name_list
    assert "P1" in wn.pipe_name_list
    assert wn.options.hydraulic.headloss == headloss


@pytest.mark.skipif(wntr.__version__ == "1.2.0", reason="Problem with headloss conversion in older wntr versions")
@pytest.mark.parametrize(
    ("headloss", "unit", "expected_roughness"),
    [
        ("H-W", "LPS", 100),
        ("D-W", "LPS", 0.1),
        ("C-M", "LPS", 100),
        ("H-W", "SI", 100),
        ("D-W", "SI", 100),
        ("C-M", "SI", 100),
        ("H-W", "GPM", 100),
        ("D-W", "GPM", 0.030480000000000004),
        ("C-M", "GPM", 100),
    ],
)
@pytest.mark.filterwarnings("ignore: QgsField constructor is deprecated")
def test_roughness_conversion(simple_layers, headloss, unit, expected_roughness):
    wn = wntrqgis.from_qgis(simple_layers, unit, headloss=headloss)
    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert wn.get_link("P1").roughness == expected_roughness


@pytest.mark.filterwarnings("ignore: QgsField constructor is deprecated")
@pytest.mark.skipif(wntr.__version__ == "1.2.0", reason="Problem with headloss conversion in older wntr versions")
@pytest.mark.filterwarnings("ignore:Changing the headloss formula")
@pytest.mark.parametrize(
    ("headloss", "unit", "expected_roughness"),
    [
        ("H-W", "LPS", 100),
        ("D-W", "LPS", 0.1),
        ("C-M", "LPS", 100),
        ("H-W", "SI", 100),
        ("D-W", "SI", 100),
        ("C-M", "SI", 100),
        ("H-W", "GPM", 100),
        ("D-W", "GPM", 0.030480000000000004),
        ("C-M", "GPM", 100),
    ],
)
@pytest.mark.filterwarnings("ignore: QgsField constructor is deprecated")
def test_roughness_conversion_with_wn_options(simple_layers, headloss, unit, expected_roughness):
    wn = wntr.network.WaterNetworkModel()
    wn.options.hydraulic.headloss = headloss

    wn = wntrqgis.from_qgis(simple_layers, unit, wn=wn)
    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert wn.get_link("P1").roughness == expected_roughness


def test_from_qgis_invalid_headloss(simple_layers):
    with pytest.raises(ValueError, match="headloss must be set if wn is not set: possible values are: H-W, D-W, C-M"):
        wntrqgis.from_qgis(simple_layers, "LPS", headloss=None)


def test_from_qgis_invalid_headloss_with_wn(simple_layers):
    wn = wntr.network.WaterNetworkModel()
    with pytest.raises(
        ValueError,
        match="Cannot set headloss when wn is set. Set the headloss in the wn.options.hydraulic.headloss instead",
    ):
        wntrqgis.from_qgis(simple_layers, "LPS", headloss="INVALID", wn=wn)


def test_duplicate_names():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    add_point(junction_layer, (2, 2), ["J1"])  # Conflict: same name as the first junction
    add_point(junction_layer, (3, 3), ["J1"])
    add_point(junction_layer, (3, 3), ["J2"])
    add_point(junction_layer, (3, 3), ["J2"])

    pipe_layer = layer("linestring", [("name", str)])
    add_line(pipe_layer, [(1, 1), (2, 2)], ["P1"])
    add_line(pipe_layer, [(2, 2), (3, 3)], ["P1"])  # Conflict: same name as the first pipe

    layers = {"JUNCTIONS": junction_layer, "PIPES": pipe_layer}

    with pytest.raises(wntrqgis.interface.NetworkModelError, match="Duplicate names found: J1, J2"):
        wntrqgis.from_qgis(layers, "LPS", "H-W")


def test_name_generation_with_conflicts():
    junctions = layer("point", [("name", str)])
    add_point(junctions, (1, 1), [""])
    add_point(junctions, (2, 2), ["1"])
    add_point(junctions, (3, 3), [""])

    tanks = layer("point", [("name", str)])
    add_point(tanks, (5, 1), ["xx"])
    add_point(tanks, (6, 2), ["0"])
    add_point(tanks, (7, 3))

    reservoirs = layer("point")
    add_point(reservoirs, (8, 1))
    add_point(reservoirs, (9, 2))

    pipes = layer("linestring", [("name", str)])
    add_line(pipes, [(1, 1), (2, 2)], ["1"])
    add_line(pipes, [(2, 2), (3, 3)], [""])  # Conflict: same name as the first pipe

    layers = {"JUNCTIONS": junctions, "TANKS": tanks, "RESERVOIRS": reservoirs, "PIPES": pipes}

    wn = wntrqgis.from_qgis(layers, "LPS", "H-W")

    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert len(wn.junction_name_list) == 3
    assert len(wn.pipe_name_list) == 2
    assert wn.node_name_list == ["2", "1", "3", "4", "5", "xx", "0", "6"]
    assert wn.link_name_list == ["1", "2"]


@pytest.mark.parametrize(
    ("unit", "expected_demand"),
    {("GPM", 6.30901964e-05), ("SI", 1), ("sI", 1), ("LPS", 0.001), ("lps", 0.001), ("CFS", 0.0283168466)},
)
def test_unit_conversion_demand(simple_layers, unit, expected_demand):
    wn = wntrqgis.from_qgis(simple_layers, unit, "H-W")
    assert wn.get_node("J1").base_demand == expected_demand


def test_bad_units(simple_layers):
    with pytest.raises(
        ValueError,
        match="Units 'NON-EXISTANT' is not a known set of units. Possible units are: LPS, LPM, MLD, CMH, CFS, GPM, MGD, IMGD, AFD, SI",  # noqa: E501
    ):
        wntrqgis.from_qgis(simple_layers, units="Non-existant", headloss="H-W")


def test_length_measurement_4326(simple_layers):
    wn = wntrqgis.from_qgis(simple_layers, "LPS", "H-W")

    assert isinstance(wn, wntr.network.WaterNetworkModel)
    pipe = wn.get_link("P1")
    assert pipe.length == 556597.4539663679


# def test_length_measurement_4326_ellipsoidal(qgis_new_project, simple_layers):
#     wn = wntrqgis.from_qgis(simple_layers, "LPS", "H-W", crs="EPSG:7030")

#     assert isinstance(wn, wntr.network.WaterNetworkModel)
#     pipe = wn.get_link("P1")
#     assert pipe.length == 556597.4539663679


def test_length_measurement_utm(simple_layers):
    for layer in simple_layers.values():
        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32600"))

    wn = wntrqgis.from_qgis(simple_layers, "LPS", "H-W")
    assert isinstance(wn, wntr.network.WaterNetworkModel)
    pipe = wn.get_link("P1")
    assert pipe.length == 5.0
