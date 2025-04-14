import pytest
import wntr
from qgis.core import (
    QgsGeometry,
    QgsPoint,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

import wntrqgis.elements
from wntrqgis.interface import (
    NetworkModelError,
    UnitError,
    Writer,
    _Converter,
    _Curves,
    _Patterns,
    _SpatialIndex,
    check_network,
)


@pytest.fixture
def wn():
    return wntr.network.WaterNetworkModel()


@pytest.fixture
def qgis_project():
    return QgsProject.instance()


@pytest.fixture
def qgs_layer():
    return QgsVectorLayer("Point", "test_layer", "memory")


def test_converter_init(wn):
    converter = _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)
    assert converter._flow_units == wntr.epanet.FlowUnits.LPS
    assert not converter._darcy_weisbach


def test_converter_to_si(wn):
    converter = _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)
    value = converter.to_si(1.0, wntrqgis.elements.ModelField.ELEVATION)
    assert value == 1.0


def test_converter_from_si(wn):
    converter = _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)
    value = converter.from_si(1.0, wntrqgis.elements.ModelField.ELEVATION)
    assert value == 1.0


def test_converter_invalid_units():
    with pytest.raises(UnitError):
        _Converter("INVALID_UNIT", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)


def test_patterns_add(wn):
    patterns = _Patterns(wn)
    pattern_name = patterns.add("1 2 3")
    assert pattern_name == "2"


def test_patterns_get(wn):
    patterns = _Patterns(wn)
    pattern_name = patterns.add("1 2 3")
    pattern = patterns.get(pattern_name)
    assert pattern == "1.0 2.0 3.0"


def test_patterns_add_invalid():
    patterns = _Patterns(wntr.network.WaterNetworkModel())
    assert patterns.add(None) is None
    assert patterns.add("") is None


def test_curves_add_one(wn):
    curves = _Curves(wn, _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS))
    curve_name = curves._add_one("[(1,2), (3,4)]", _Curves.Type.HEAD)
    assert curve_name == "1"


def test_curves_get(wn):
    curves = _Curves(wn, _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS))
    curve_name = curves._add_one("[(1,2), (3,4)]", _Curves.Type.HEAD)
    curve = curves.get(curve_name)
    assert curve == "[(1.0, 2), (3.0, 4)]"


def test_curves_add_invalid(wn):
    curves = _Curves(wn, _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS))
    assert curves._add_one(None, _Curves.Type.HEAD) is None
    assert curves._add_one("", _Curves.Type.HEAD) is None


def test_writer_get_qgsfields(wn):
    writer = Writer(wn)
    fields = writer.get_qgsfields(wntrqgis.elements.ModelLayer.JUNCTIONS)
    assert isinstance(fields, wntrqgis.elements.QgsFields)


def test_writer_write(wn, qgs_layer):
    wn.add_junction("J1", base_demand=0.01, elevation=10)
    wn.add_junction("J2", base_demand=0.02, elevation=20)
    wn.add_pipe("P1", "J1", "J2", length=100, diameter=0.3, roughness=100)

    writer = Writer(wn)
    sink = qgs_layer.dataProvider()
    writer.write(wntrqgis.elements.ModelLayer.JUNCTIONS, sink)
    assert sink.featureCount() > 0


def test_writer_write_no_features(wn, qgs_layer):
    writer = Writer(wn)
    sink = qgs_layer.dataProvider()
    writer.write(wntrqgis.elements.ModelLayer.JUNCTIONS, sink)
    assert sink.featureCount() == 0


def test_spatial_index_add_node():
    index = _SpatialIndex()
    geometry = QgsGeometry(QgsPoint(1, 1))
    index.add_node(geometry, "node1")
    assert len(index._nodelist) == 1


def test_spatial_index_snap_link():
    index = _SpatialIndex()
    geometry = QgsGeometry.fromPolyline([QgsPoint(1, 1), QgsPoint(2, 2)])
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    index.add_node(QgsGeometry(QgsPoint(2, 2)), "node2")
    snapped_geometry, start_node, end_node = index.snap_link(geometry)
    assert start_node == "node1"
    assert end_node == "node2"


def test_spatial_index_snap_link_nearby():
    index = _SpatialIndex()
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    index.add_node(QgsGeometry(QgsPoint(2, 2)), "node2")
    geometry = QgsGeometry.fromPolyline([QgsPoint(1.01, 1.01), QgsPoint(1.92, 1.92)])
    snapped_geometry, start_node, end_node = index.snap_link(geometry)
    assert start_node == "node1"
    assert end_node == "node2"
    assert snapped_geometry.asPolyline() == [QgsPointXY(1, 1), QgsPointXY(2, 2)]


def test_spatial_index_snap_link_far_apart():
    index = _SpatialIndex()
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    index.add_node(QgsGeometry(QgsPoint(2, 2)), "node2")
    geometry = QgsGeometry.fromPolyline([QgsPoint(10, 10), QgsPoint(20, 20)])
    with pytest.raises(RuntimeError, match=r"nearest node to snap to is too far \(node2\)"):
        index.snap_link(geometry)


def test_spatial_index_snap_link_same_node():
    index = _SpatialIndex()
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    geometry = QgsGeometry.fromPolyline([QgsPoint(1.01, 1.01), QgsPoint(2, 3), QgsPoint(1.02, 1.02)])
    with pytest.raises(RuntimeError, match="connects to the same node on both ends"):
        index.snap_link(geometry)


def test_spatial_index_snap_link_multi_part():
    index = _SpatialIndex()
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    index.add_node(QgsGeometry(QgsPoint(2, 2)), "node2")
    geometry = QgsGeometry.fromMultiPolylineXY(
        [[QgsPointXY(1, 1), QgsPointXY(2, 2)], [QgsPointXY(3, 3), QgsPointXY(4, 4)]]
    )
    with pytest.raises(RuntimeError, match="All links must be single part lines"):
        index.snap_link(geometry)


def test_spatial_index_snap_link_invalid_geometry():
    index = _SpatialIndex()
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    index.add_node(QgsGeometry(QgsPoint(2, 2)), "node2")
    geometry = QgsGeometry()  # Invalid geometry
    with pytest.raises(RuntimeError, match="All links must have valid geometry"):
        index.snap_link(geometry)


def test_check_network_no_junctions(wn):
    with pytest.raises(NetworkModelError, match="At least one junction is necessary"):
        check_network(wn)


def test_check_network_no_tanks_or_reservoirs(wn):
    wn.add_junction("j1")
    wn.add_junction("j2")
    wn.add_pipe("p1", "j1", "j2")
    with pytest.raises(NetworkModelError, match="At least one tank or reservoir is required"):
        check_network(wn)


def test_check_network_no_links(wn):
    wn.add_junction("j1")
    wn.add_junction("j2")
    wn.add_tank("t1")
    with pytest.raises(NetworkModelError, match=r"At least one link \(pipe, pump or valve\) is necessary"):
        check_network(wn)


def test_check_network_orphan_nodes(wn):
    wn.add_junction("j1")
    wn.add_junction("j2")
    wn.add_tank("t1")
    wn.add_pipe("p1", "j1", "j2")
    with pytest.raises(NetworkModelError, match="the following nodes are not connected to any links: t1"):
        check_network(wn)


def test_check_network_valid(wn):
    wn.add_junction("j1")
    wn.add_junction("j2")
    wn.add_tank("t1")
    wn.add_pipe("p1", "j1", "j2")
    wn.add_pipe("p2", "j2", "t1")
    try:
        check_network(wn)
    except NetworkModelError:
        pytest.fail("check_network raised NetworkModelError unexpectedly!")


def test_get_field_groups(wn):
    from wntrqgis.elements import FieldGroup

    assert wntrqgis.interface._get_field_groups(wn) == FieldGroup(0)

    wn.options.quality.parameter = "CHEMICAL"
    wn.options.report.energy = "YES"
    wn.options.hydraulic.demand_model = "PDD"
    assert (
        wntrqgis.interface._get_field_groups(wn)
        == FieldGroup.PRESSURE_DEPENDENT_DEMAND | FieldGroup.ENERGY | FieldGroup.WATER_QUALITY_ANALYSIS
    )
