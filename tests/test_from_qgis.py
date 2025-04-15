from __future__ import annotations

import pytest
from qgis.core import NULL, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer

import wntrqgis


def layer(
    layer_type: str, fields: list[tuple[str, type | str]] | None = None, crs: str | None = None
) -> QgsVectorLayer:
    if not fields:
        fields = []
    field_string = "&".join([f"field={name}:{type_to_string(the_type)}" for name, the_type in fields])
    crs_string = f"crs={crs}" if crs else "crs=None"
    return QgsVectorLayer(f"{layer_type}?{crs_string}&{field_string}", "", "memory")


def type_to_string(the_type: type | str) -> str:
    if isinstance(the_type, str):
        return the_type
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


def add_point(layer: QgsVectorLayer, point: tuple[float, float], fields: list | None = None):
    if not fields:
        fields = []
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*point)))
    feature.setAttributes(fields)
    layer.dataProvider().addFeature(feature)
    layer.updateExtents()


def add_line(layer: QgsVectorLayer, points: list[tuple[float, float]], fields: list | None = None):
    if not fields:
        fields = []
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in points]))
    feature.setAttributes(fields)
    layer.dataProvider().addFeature(feature)
    layer.updateExtents()


@pytest.fixture
def simple_layers():
    junction_layer = layer("point", [("name", str), ("base_demand", float)])
    add_point(junction_layer, (1, 1), ["J1", 1])
    tank_layer = layer("point", [("name", str)])
    add_point(tank_layer, (4, 5), ["T1"])
    pipe_layer = layer("linestring", [("name", str), ("roughness", float)])
    add_line(pipe_layer, [(1, 1), (4, 5)], ["P1", 100])
    return {"JUNCTIONS": junction_layer, "PIPES": pipe_layer, "TANKS": tank_layer}


@pytest.fixture
def all_layers():
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

    return {
        "JUNCTIONS": junction_layer,
        "TANKS": tank_layer,
        "RESERVOIRS": reservoir_layer,
        "PIPES": pipe_layer,
        "PUMPS": pump_layer,
        "VALVES": valve_layer,
    }


def test_simple_layers(simple_layers):
    import wntr

    wn = wntrqgis.from_qgis(simple_layers, "LPS", "H-W")

    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert "J1" in wn.junction_name_list


def test_broken_layername(simple_layers):
    simple_layers["wrongname"] = simple_layers["JUNCTIONS"]

    with pytest.raises(ValueError, match="'wrongname' is not a valid layer type."):
        wntrqgis.from_qgis(simple_layers, "LPS", "H-W")


def test_minimum_attributes(all_layers):
    import wntr

    wn = wntrqgis.from_qgis(all_layers, "LPS", "H-W")

    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert "1" in wn.junction_name_list
    assert "2" in wn.junction_name_list
    assert "4" in wn.tank_name_list
    assert "3" in wn.reservoir_name_list
    assert "1" in wn.pipe_name_list
    assert "2" in wn.pump_name_list
    assert "3" in wn.valve_name_list


def test_no_pipes(all_layers):
    import wntr

    del all_layers["PIPES"]

    wn = wntrqgis.from_qgis(all_layers, "LPS", "H-W")

    assert isinstance(wn, wntr.network.WaterNetworkModel)


def test_no_links():
    all_layers = {"JUNCTIONS": layer("point", [("name", str)]), "PIPES": layer("linestring", [("name", str)])}
    add_point(all_layers["JUNCTIONS"], (1, 1), ["J1"])

    with pytest.raises(wntrqgis.interface.NetworkModelError, match="There are no links in the model"):
        wntrqgis.from_qgis(all_layers, "LPS", "H-W")


def test_no_nodes():
    all_layers = {"JUNCTIONS": layer("point"), "PIPES": layer("linestring", [("name", str)])}
    add_line(all_layers["PIPES"], [(1, 1)], ["P1"])

    with pytest.raises(wntrqgis.interface.NetworkModelError, match="There are no nodes in the model"):
        wntrqgis.from_qgis(all_layers, "LPS", "H-W")


def test_wntr_error():
    all_layers = {
        "JUNCTIONS": layer("point", [("name", str)]),
        "PUMPS": layer("linestring", [("name", str), ("pump_type", str)]),
    }
    add_point(all_layers["JUNCTIONS"], (1, 1), ["J1"])
    add_point(all_layers["JUNCTIONS"], (2, 2), ["J2"])
    add_line(all_layers["PUMPS"], [(1, 1), (2, 2)], ["P1", "NOT_A_PUMP_TYPE"])

    with pytest.raises(wntrqgis.interface.WntrError, match="error from WNTR. pump_parameter must be a float or string"):
        wntrqgis.from_qgis(all_layers, "LPS", "H-W")


@pytest.mark.skip("Can't find out how to make an infinite line")
def test_infinite_pipe():
    junction_layer = layer("point", [("name", str)], "EPSG:4326")
    add_point(junction_layer, (1, 1), ["J1"])
    add_point(junction_layer, (400, 400), ["J2"])
    pipe_layer = layer("linestring", [("name", str)], "EPSG:4326")
    add_line(pipe_layer, [(1, 1), (400, 400)], ["P1"])
    layers = {"JUNCTIONS": junction_layer, "PIPES": pipe_layer}

    with pytest.raises(wntrqgis.interface.NetworkModelError, match="Infinite length is not allowed"):
        wntrqgis.from_qgis(layers, "LPS", "H-W", crs="EPSG:3089")


@pytest.mark.parametrize("headloss", ["H-W", "D-W", "C-M"])
def test_from_qgis_headloss(simple_layers, headloss):
    wn = wntrqgis.from_qgis(simple_layers, "LPS", headloss=headloss)

    assert "J1" in wn.junction_name_list
    assert "T1" in wn.tank_name_list
    assert "P1" in wn.pipe_name_list
    assert wn.options.hydraulic.headloss == headloss


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
    import wntr

    if wntr.__version__ == "1.2.0" and headloss == "D-W":
        pytest.skip("Problem with headloss conversion in older wntr versions")

    wn = wntrqgis.from_qgis(simple_layers, unit, headloss=headloss)
    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert wn.get_link("P1").roughness == expected_roughness


@pytest.mark.filterwarnings("ignore: QgsField constructor is deprecated")
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
    import wntr

    if wntr.__version__ == "1.2.0" and headloss == "D-W":
        pytest.skip("Problem with headloss conversion in older wntr versions")

    wn = wntr.network.WaterNetworkModel()
    wn.options.hydraulic.headloss = headloss

    wn = wntrqgis.from_qgis(simple_layers, unit, wn=wn)
    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert wn.get_link("P1").roughness == expected_roughness


def test_from_qgis_invalid_headloss(simple_layers):
    with pytest.raises(ValueError, match="headloss must be set if wn is not set: possible values are: H-W, D-W, C-M"):
        wntrqgis.from_qgis(simple_layers, "LPS", headloss=None)


def test_from_qgis_invalid_headloss_with_wn(simple_layers):
    import wntr

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
        match="'NON-EXISTANT' is not a known set of units. Possible units are: LPS, LPM, MLD, CMH, CFS, GPM, MGD, IMGD, AFD, SI",  # noqa: E501
    ):
        wntrqgis.from_qgis(simple_layers, units="Non-existant", headloss="H-W")


def test_length_measurement_utm(simple_layers):
    for layer in simple_layers.values():
        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32600"))

    wn = wntrqgis.from_qgis(simple_layers, "LPS", "H-W")

    pipe = wn.get_link("P1")
    assert pipe.length == 5.0


def test_custom_attributes():
    # Create layers directly
    junction_layer = layer(
        "point",
        [
            ("name", str),
            ("base_demand", float),
            ("custom_str", str),
            ("custom_int", int),
            ("custom_float", float),
            ("custom_bool", bool),
        ],
    )
    add_point(junction_layer, (1, 1), ["J1", 1, "xx", 2, 2.5, True])
    add_point(junction_layer, (2, 2), ["J2", 2, "yy", 1000000000, 7.2, False])

    pipe_layer = layer("linestring", [("name", str), ("roughness", float)])
    add_line(pipe_layer, [(1, 1), (2, 2)], ["P1", 100])

    layers = {"JUNCTIONS": junction_layer, "PIPES": pipe_layer}

    wn = wntrqgis.from_qgis(layers, "LPS", "H-W")

    assert wn.get_node("J1").custom_str == "xx"
    assert wn.get_node("J1").custom_int == 2
    assert wn.get_node("J1").custom_float == 2.5
    assert wn.get_node("J1").custom_bool is True

    assert wn.get_node("J2").custom_str == "yy"
    assert wn.get_node("J2").custom_int == 1000000000
    assert wn.get_node("J2").custom_float == 7.2
    assert wn.get_node("J2").custom_bool is False


@pytest.fixture
def layers_that_snap():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (0, 0), ["J1"])
    tank_layer = layer("point", [("name", str)])
    add_point(tank_layer, (3000, 4000), ["T1"])
    pipe_layer = layer("linestring", [("name", str)])
    add_line(pipe_layer, [(1, 1), (2800, 3800)], ["P1"])
    return {"JUNCTIONS": junction_layer, "PIPES": pipe_layer, "TANKS": tank_layer}


def test_snap_nodes(layers_that_snap):
    wn = wntrqgis.from_qgis(layers_that_snap, "LPS", "H-W")

    assert "P1" in wn.pipe_name_list
    assert wn.get_link("P1").start_node_name == "J1"
    assert wn.get_link("P1").end_node_name == "T1"


@pytest.fixture
def mixed_crs_layers():
    junction_layer = layer("point", [("name", str)], "EPSG:4326")
    add_point(junction_layer, (-83, 38), ["J1"])
    tank_layer = layer("point", [("name", str)], "EPSG:32616")
    add_point(tank_layer, (844219, 4230929), ["T1"])
    pipe_layer = layer("linestring", [("name", str), ("roughness", float)], "EPSG:3089")
    add_line(pipe_layer, [(5713511, 3899366), (5691228, 3957214)], ["P1", 100])
    return {"JUNCTIONS": junction_layer, "PIPES": pipe_layer, "TANKS": tank_layer}


def test_snap_nodes_mixed_crs(mixed_crs_layers):
    wn = wntrqgis.from_qgis(mixed_crs_layers, "LPS", "H-W")

    assert "P1" in wn.pipe_name_list
    assert wn.get_link("P1").start_node_name == "J1"
    assert wn.get_link("P1").end_node_name == "T1"


@pytest.mark.parametrize("crs", ["EPSG:32616", "EPSG:3089"])
def test_snap_nodes_mixed_crs_with_crs_specified(mixed_crs_layers, crs):
    wn = wntrqgis.from_qgis(mixed_crs_layers, "LPS", "H-W", crs=crs)
    assert wn.get_link("P1").length == pytest.approx(18900, 0.01)


def test_snap_nodes_mixed_crs_length(mixed_crs_layers):
    wn = wntrqgis.from_qgis(mixed_crs_layers, "LPS", "H-W")
    assert wn.get_link("P1").length == pytest.approx(19569, 0.01)


def test_snap_nodes_mixed_crs_simple():
    junction_layer = layer("point", [("name", str)], "EPSG:4326")
    add_point(junction_layer, (-83, 38), ["J1"])
    tank_layer = layer("point", [("name", str)], "EPSG:4326")
    add_point(tank_layer, (-84, 39), ["T1"])
    pipe_layer = layer("linestring", [("name", str), ("roughness", float)], "EPSG:3857")
    add_line(pipe_layer, [(-9239517, 4579425), (-9350837, 4721671)], ["P1", 100])
    layers = {"JUNCTIONS": junction_layer, "PIPES": pipe_layer, "TANKS": tank_layer}
    wn = wntrqgis.from_qgis(layers, "LPS", "H-W")

    assert "P1" in wn.pipe_name_list
    assert wn.get_link("P1").start_node_name == "J1"
    assert wn.get_link("P1").end_node_name == "T1"


def test_snap_length(layers_that_snap):
    wn = wntrqgis.from_qgis(layers_that_snap, "LPS", "H-W")
    assert wn.get_link("P1").length == 5000


def test_too_far_to_snap():
    junction_layer = layer("point", [("name", str), ("base_demand", float), ("length", float)])
    add_point(junction_layer, (1, 1), ["J1", 1])
    tank_layer = layer("point", [("name", str)])
    add_point(tank_layer, (1000, 1000), ["T1"])
    pipe_layer = layer("linestring", [("name", str), ("roughness", float)])
    add_line(pipe_layer, [(1, 1), (900, 900)], ["P1", 100])
    layers = {"JUNCTIONS": junction_layer, "PIPES": pipe_layer, "TANKS": tank_layer}

    with pytest.raises(wntrqgis.interface.NetworkModelError, match="nearest node to snap to is too far"):
        wntrqgis.from_qgis(layers, "LPS", "H-W")


def test_measure_no_crs(simple_layers):
    wn = wntrqgis.from_qgis(simple_layers, "LPS", "H-W")

    assert wn.get_link("P1").length == 5.0


def test_measure_utm(simple_layers):
    # 32636 is a utm crs
    wn = wntrqgis.from_qgis(simple_layers, "LPS", "H-W", crs="EPSG:32636")

    assert wn.get_link("P1").length == 5.0


def test_measure_feet(simple_layers):
    # 3089 is a feet crs
    wn = wntrqgis.from_qgis(simple_layers, "LPS", "H-W", crs="EPSG:3089")

    assert wn.get_link("P1").length == pytest.approx(5.0 / 3.2808, 0.01)


def test_prioritise_length_attribute():
    junction_layer = layer("point", [("name", str), ("base_demand", float)])
    add_point(junction_layer, (1, 1), ["J1", 1])
    add_point(junction_layer, (4, 5), ["J2"])
    pipe_layer = layer("linestring", [("name", str), ("length", float)])
    add_line(pipe_layer, [(1, 1), (4, 5)], ["P1"])
    add_line(pipe_layer, [(1, 1), (4, 5)], ["P2", 100])
    layers = {"JUNCTIONS": junction_layer, "PIPES": pipe_layer}

    warn_message = r"1 pipe\(s\) have very different attribute length vs measured length. First five are: P2 \(5 metres vs 100 metres\)"  # noqa: E501
    with pytest.warns(UserWarning, match=warn_message):
        wn = wntrqgis.from_qgis(layers, "LPS", "H-W")

    assert wn.get_link("P1").length == 5
    assert wn.get_link("P2").length == 100


@pytest.mark.parametrize(
    ("bool_attr", "expected_result", "field_type"),
    [
        (1, True, int),
        (0, False, int),
        (True, True, bool),
        (False, False, bool),
        ("True", True, str),
        ("False", False, str),
        ("1", True, str),
        ("0", False, str),
        (1.0, True, float),
        (0.0, False, float),
        ("1.0", True, str),
        ("0.0", False, str),
        (NULL, False, float),
    ],
)
def test_boolean_attributes(bool_attr, expected_result, field_type):
    if bool_attr in ["True", "False"]:
        pytest.skip("String True/False Boolean attributes are not supported in WNTR yet")

    junction_layer = layer("point", [("name", str), ("base_demand", float)])
    add_point(junction_layer, (1, 1), ["J1", 1])
    tank_layer = layer("point", [("name", str), ("overflow", field_type)])
    add_point(tank_layer, (4, 5), ["T1", bool_attr])
    pipe_layer = layer("linestring", [("name", str), ("check_valve", field_type)])
    add_line(pipe_layer, [(1, 1), (4, 5)], ["P1", bool_attr])

    layers = {"JUNCTIONS": junction_layer, "TANKS": tank_layer, "PIPES": pipe_layer}

    wn = wntrqgis.from_qgis(layers, "LPS", "H-W")

    assert wn.get_link("P1").check_valve is expected_result
    assert wn.get_node("T1").overflow is expected_result


@pytest.mark.parametrize(
    ("float_attr", "expected_result", "field_type"),
    [
        (1, 1.0, int),
        (0, 0.0, int),
        ("1", 1.0, str),
        ("0", 0.0, str),
        (1.1, 1.1, float),
        (0.0, 0.0, float),
        ("1.1", 1.1, str),
        ("0.0", 0.0, str),
    ],
)
def test_float_attributes(float_attr, expected_result, field_type):
    if float_attr in ["True", "False"]:
        pytest.skip("String True/False Boolean attributes are not supported in WNTR yet")

    junction_layer = layer("point", [("name", str), ("elevation", field_type), ("pressure_exponent", field_type)])
    add_point(junction_layer, (1, 1), ["J1", float_attr, float_attr])
    # additionally check that 'elevation' can accept mixed types
    tank_layer = layer("point", [("name", str), ("diameter", field_type), ("elevation", float)])
    add_point(tank_layer, (4, 5), ["T1", float_attr, 865.0])
    pipe_layer = layer("linestring", [("name", str), ("length", field_type), ("diameter", field_type)])
    add_line(pipe_layer, [(1, 1), (4, 5)], ["P1", float_attr, float_attr])

    layers = {"JUNCTIONS": junction_layer, "TANKS": tank_layer, "PIPES": pipe_layer}

    wn = wntrqgis.from_qgis(layers, "lps", "H-W")
    assert wn.get_node("J1").elevation == expected_result
    assert wn.get_node("J1").pressure_exponent == expected_result
    assert wn.get_node("T1").diameter == expected_result
    assert wn.get_node("T1").elevation == 865.0
    assert wn.get_link("P1").length == expected_result
    assert wn.get_link("P1").diameter == expected_result / 1000


def test_float_error():
    junction_layer = layer("point")
    add_point(junction_layer, (1, 1))
    add_point(junction_layer, (4, 5))
    pipe_layer = layer("linestring", [("name", str), ("diameter", str)])
    add_line(pipe_layer, [(1, 1), (4, 5)], ["P1", "not_a_float"])

    layers = {"JUNCTIONS": junction_layer, "PIPES": pipe_layer}

    with pytest.raises(
        wntrqgis.interface.NetworkModelError, match='Problem in column diameter: Unable to parse string "not_a_float"'
    ):
        wntrqgis.from_qgis(layers, "LPS", "H-W")


def test_demand_pattern():
    junction_layer = layer("point", [("name", str), ("base_demand", float), ("demand_pattern", str)])
    add_point(junction_layer, (1, 1), ["J1", 1, "1 0 2.5 -3"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("power", float)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "POWER", 10])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")

    assert wn.get_node("J1").demand_timeseries_list[0].pattern_name == "2"
    assert list(wn.patterns["2"].multipliers) == [1, 0, 2.5, -3]


def test_head_pattern():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    reservoir_layer = layer("point", [("name", str), ("head_pattern", str)])
    add_point(reservoir_layer, (4, 5), ["R1", "2 0 200.5"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("power", float)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "POWER", 10])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")

    assert wn.get_node("R1").head_pattern_name == "2"
    assert list(wn.patterns["2"].multipliers) == [2, 0, 200.5]


@pytest.mark.skip(reason="Energy pattern bug in wntr")
def test_energy_pattern():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("power", float), ("energy_pattern", str)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "POWER", 10, "5 4 3 2 1 1"])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")

    assert wn.get_link("P1").energy_pattern == "2"
    assert list(wn.patterns["2"].multipliers) == [5, 4, 3, 2, 1, 1, 1]


def test_speed_pattern():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("power", float), ("speed_pattern", str)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "POWER", 10, "5 4 3 2 1 1"])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")

    assert wn.get_link("P1").speed_pattern_name == "2"
    assert list(wn.patterns["2"].multipliers) == [5.0, 4.0, 3.0, 2.0, 1.0, 1.0]


def test_lots_of_patterns():
    junction_layer = layer("point", [("name", str), ("base_demand", float), ("demand_pattern", str)])
    add_point(junction_layer, (1, 1), ["J1", 1, "1 0 2.5"])
    add_point(junction_layer, (2, 2), ["J2", 1, "1 0 2.5"])
    add_point(junction_layer, (3, 3), ["J3", 1, "1 0 3.0"])

    reservoir_layer = layer("point", [("name", str), ("head_pattern", str)])
    add_point(reservoir_layer, (4, 5), ["R1", "2 0 200.5"])
    add_point(reservoir_layer, (5, 6), ["R2"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("power", float), ("speed_pattern", str)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "POWER", 10, "5 4 3 2 1 1"])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}
    wn = wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")

    assert wn.get_node("J1").demand_timeseries_list[0].pattern_name == "2"
    assert wn.get_node("J2").demand_timeseries_list[0].pattern_name == "2"
    assert wn.get_node("J3").demand_timeseries_list[0].pattern_name == "3"
    assert wn.get_node("R1").head_pattern_name == "4"
    assert wn.get_node("R2").head_pattern_name is None
    assert wn.get_link("P1").speed_pattern_name == "5"


def test_bad_pattern():
    junction_layer = layer("point", [("name", str), ("base_demand", float), ("demand_pattern", str)])
    add_point(junction_layer, (1, 1), ["J1", 1, "1 0 2,5"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])
    pipe_layer = layer("linestring", [("name", str), ("roughness", float)])
    add_line(pipe_layer, [(1, 1), (4, 5)], ["P1", 100])
    pattern_layers = {"JUNCTIONS": junction_layer, "PIPES": pipe_layer, "RESERVOIRS": reservoir_layer}
    with pytest.raises(wntrqgis.interface.PatternError, match="could not convert string to float: '2,5'"):
        wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")


def test_float_list_pattern():
    junction_layer = layer("point", [("name", str), ("base_demand", float), ("demand_pattern", "double[]")])
    add_point(junction_layer, (1, 1), ["J1", 1, [1.0, 0.0, 2.5]])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("power", float)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "POWER", 10])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")

    assert wn.get_node("J1").demand_timeseries_list[0].pattern_name == "2"
    assert list(wn.patterns["2"].multipliers) == [1, 0, 2.5]


def test_str_list_pattern():
    junction_layer = layer("point", [("name", str), ("base_demand", float), ("demand_pattern", "string[]")])
    add_point(junction_layer, (1, 1), ["J1", 1, ["1.0", "0.0", "2.5"]])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("power", float)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "POWER", 10])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")

    assert wn.get_node("J1").demand_timeseries_list[0].pattern_name == "2"
    assert list(wn.patterns["2"].multipliers) == [1, 0, 2.5]


def test_int_list_pattern():
    junction_layer = layer("point", [("name", str), ("base_demand", float), ("demand_pattern", "integer[]")])
    add_point(junction_layer, (1, 1), ["J1", 1, [1, 0, -1, 100]])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("power", float)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "POWER", 10])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")

    assert wn.get_node("J1").demand_timeseries_list[0].pattern_name == "2"
    assert list(wn.patterns["2"].multipliers) == [1, 0, -1, 100]


def test_double_list_pattern():
    junction_layer = layer("point", [("name", str), ("base_demand", float), ("demand_pattern", "integer[]")])
    add_point(junction_layer, (1, 1), ["J1", 1, [1, 0, -1, 100]])
    add_point(junction_layer, (1, 2), ["J2", 1, [1, 0, -1, 100]])

    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("power", float)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "POWER", 10])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")

    assert wn.get_node("J1").demand_timeseries_list[0].pattern_name == "2"
    assert wn.get_node("J2").demand_timeseries_list[0].pattern_name == "2"
    assert list(wn.patterns["2"].multipliers) == [1, 0, -1, 100]


def test_head_curve_no_conversion():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("pump_curve", str)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "HEAD", "[(0.0, 200.5),(1.0,50)]"])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "SI", "H-W")

    assert wn.get_link("P1").pump_curve_name == "1"
    assert wn.curves["1"].points == [(0.0, 200.5), (1.0, 50)]


def test_head_curve_conversion():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("pump_curve", str)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "HEAD", "[(0.0, 200.5),(1.0,50)]"])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")

    assert wn.get_link("P1").pump_curve_name == "1"
    assert wn.curves["1"].points == [(0.0, 200.5), (0.001, 50)]


def test_head_curve_conversion_feet():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("pump_curve", str)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "HEAD", "[(0.0, 10),(1.0,100.0)]"])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "CFS", "H-W")

    assert wn.get_link("P1").pump_curve_name == "1"
    assert wn.curves["1"].points == [(0.0, 3.048), (0.0283168466, 30.48)]


def test_curve_error():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("pump_curve", str)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "HEAD", "[(0.0, 200.5),(1.0,x)]"])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    with pytest.raises(wntrqgis.interface.CurveError, match="problem reading pump head curve"):
        wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")


def test_curve_error2():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("pump_curve", str)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "HEAD", "assert False"])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    with pytest.raises(wntrqgis.interface.CurveError, match="problem reading pump head curve"):
        wntrqgis.from_qgis(pattern_layers, "LPS", "H-W")


def test_valve_headloss_curve():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    valve_layer = layer("linestring", [("name", str), ("valve_type", str), ("headloss_curve", str)])
    add_line(valve_layer, [(1, 1), (4, 5)], ["V1", "GPV", "[(0.0, 200.5),(1.0,50)]"])
    layers = {"JUNCTIONS": junction_layer, "VALVES": valve_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(layers, "CFS", "H-W")

    assert wn.get_link("V1").headloss_curve_name == "1"
    assert wn.curves["1"].points == [(0.0, 61.1124), (0.0283168466, 15.24)]


def test_headloss_curve_error():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    valve_layer = layer("linestring", [("name", str), ("valve_type", str), ("headloss_curve", str)])
    add_line(valve_layer, [(1, 1), (4, 5)], ["V1", "GPV", "[(0.0, 200.5),xx 0,50)]"])
    layers = {"JUNCTIONS": junction_layer, "VALVES": valve_layer, "RESERVOIRS": reservoir_layer}

    with pytest.raises(wntrqgis.interface.CurveError, match="problem reading general purpose valve headloss curve"):
        wntrqgis.from_qgis(layers, "LPS", "H-W")


def test_volume_curve():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    tank_layer = layer("point", [("name", str), ("max_level", float), ("vol_curve", str)])
    add_point(tank_layer, (4, 5), ["T1", 20, "[(0.0,100),(10.0,1000),(20,10000.0)]"])
    pipe_layer = layer("linestring", [("name", str)])
    add_line(pipe_layer, [(1, 1), (4, 5)], ["P1"])
    layers = {"JUNCTIONS": junction_layer, "TANKS": tank_layer, "PIPES": pipe_layer}

    wn = wntrqgis.from_qgis(layers, "CFS", "H-W")

    assert wn.get_node("T1").vol_curve_name == "1"
    assert wn.curves["1"].points == [
        (0.0, 2.8316846592000005),
        (3.048, 28.316846592000005),
        (6.096, 283.16846592),
    ]


def test_volume_curve_error():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    tank_layer = layer("point", [("name", str), ("max_level", float), ("vol_curve", str)])
    add_point(tank_layer, (4, 5), ["T1", 20, "[](0.0,100),(10.0,1000),(20,10000.0)]"])
    pipe_layer = layer("linestring", [("name", str)])
    add_line(pipe_layer, [(1, 1), (4, 5)], ["P1"])
    layers = {"JUNCTIONS": junction_layer, "TANKS": tank_layer, "PIPES": pipe_layer}

    with pytest.raises(wntrqgis.interface.CurveError, match="problem reading tank volume curve"):
        wntrqgis.from_qgis(layers, "LPS", "H-W")


@pytest.mark.skip("Efficiency curve bug in wntr")
def test_efficiency_curve():
    junction_layer = layer("point", [("name", str)])
    add_point(junction_layer, (1, 1), ["J1"])
    reservoir_layer = layer("point", [("name", str)])
    add_point(reservoir_layer, (4, 5), ["R1"])

    pump_layer = layer("linestring", [("name", str), ("pump_type", str), ("power", float), ("efficiency", str)])
    add_line(pump_layer, [(1, 1), (4, 5)], ["P1", "POWER", 10, "[(1.0, 2.0)]"])
    pattern_layers = {"JUNCTIONS": junction_layer, "PUMPS": pump_layer, "RESERVOIRS": reservoir_layer}

    wn = wntrqgis.from_qgis(pattern_layers, "CFS", "H-W")

    assert wn.get_link("P1").efficiencey.multipliers == "1"


def test_null_geometry_point():
    junction_layer = layer("point")
    junction_layer.dataProvider().addFeature(QgsFeature())
    add_point(junction_layer, (1, 1))
    tank_layer = layer("point")
    tank_layer.dataProvider().addFeature(QgsFeature())
    pipe_layer = layer("linestring", [("name", str), ("roughness", float)])
    add_line(pipe_layer, [(1, 1), (4, 5)], ["P1", 100])
    layers = {"JUNCTIONS": junction_layer, "PIPES": pipe_layer, "TANKS": tank_layer}

    with pytest.raises(wntrqgis.interface.NetworkModelError, match=r"in nodes, 2 feature\(s\) have no geometry"):
        wntrqgis.from_qgis(layers, "LPS", "H-W")


def test_null_geometry_link():
    junction_layer = layer("point")
    add_point(junction_layer, (1, 1))
    add_point(junction_layer, (1, 1), ["J1", 1])
    tank_layer = layer("point", [("name", str)])
    add_point(tank_layer, (4, 5), ["T1"])
    pipe_layer = layer("linestring")
    pipe_layer.dataProvider().addFeature(QgsFeature())

    layers = {"JUNCTIONS": junction_layer, "PIPES": pipe_layer, "TANKS": tank_layer}

    with pytest.raises(wntrqgis.interface.NetworkModelError, match=r"in links, 1 feature\(s\) have no geometry"):
        wntrqgis.from_qgis(layers, "LPS", "H-W")
