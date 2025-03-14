import pytest
import wntr
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPoint,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant

import wntrqgis.elements
from wntrqgis.interface import (
    NetworkModelError,
    Writer,
    _Converter,
    _Curves,
    _get_field_groups,
    _Patterns,
    _SpatialIndex,
    check_network,
    from_qgis,
    to_qgis,
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


def test_to_qgis(wn):
    layers = to_qgis(wn)
    assert isinstance(layers, dict)
    assert "JUNCTIONS" in layers


@pytest.mark.filterwarnings("ignore:QgsField constructor is deprecated")
def test_from_qgis(wn, qgis_project, qgs_layer):
    # Add some nodes to the junctions layer
    provider = qgs_layer.dataProvider()
    provider.addAttributes([QgsField("name", QVariant.String)])
    qgs_layer.updateFields()

    feature1 = QgsFeature()
    feature1.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1, 1)))
    feature1.setAttributes(["J1"])
    provider.addFeature(feature1)

    feature2 = QgsFeature()
    feature2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(2, 2)))
    feature2.setAttributes(["J2"])
    provider.addFeature(feature2)

    qgs_layer.updateExtents()

    # Add some pipes
    pipe_layer = QgsVectorLayer("LineString", "pipes", "memory")
    pipe_provider = pipe_layer.dataProvider()
    pipe_provider.addAttributes([QgsField("name", QVariant.String)])
    pipe_layer.updateFields()

    pipe_feature = QgsFeature()
    pipe_feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(1, 1), QgsPointXY(2, 2)]))
    pipe_feature.setAttributes(["P1"])
    pipe_provider.addFeature(pipe_feature)

    pipe_layer.updateExtents()

    layers = {"JUNCTIONS": qgs_layer, "PIPES": pipe_layer}
    new_wn = from_qgis(layers, "LPS", wn, qgis_project)
    assert isinstance(new_wn, wntr.network.WaterNetworkModel)
    assert "J1" in new_wn.junction_name_list
    assert "J2" in new_wn.junction_name_list
    assert "P1" in new_wn.pipe_name_list


def test_get_field_groups(wn):
    field_groups = _get_field_groups(wn)
    assert field_groups == wntrqgis.elements.FieldGroup(0)


def test_check_network(wn):
    with pytest.raises(NetworkModelError):
        check_network(wn)


def test_patterns_add(wn):
    patterns = _Patterns(wn)
    pattern_name = patterns.add("1 2 3")
    assert pattern_name == "2"


def test_patterns_get(wn):
    patterns = _Patterns(wn)
    pattern_name = patterns.add("1 2 3")
    pattern = patterns.get(pattern_name)
    assert pattern == "1.0 2.0 3.0"


def test_curves_add_one(wn):
    curves = _Curves(wn, _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS))
    curve_name = curves._add_one("[(1,2), (3,4)]", _Curves.Type.HEAD)
    assert curve_name == "1"


def test_curves_get(wn):
    curves = _Curves(wn, _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS))
    curve_name = curves._add_one("[(1,2), (3,4)]", _Curves.Type.HEAD)
    curve = curves.get(curve_name)
    assert curve == "[(1.0, 2), (3.0, 4)]"


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


def test_check_network_no_junctions():
    wn = wntr.network.WaterNetworkModel()
    with pytest.raises(NetworkModelError, match="At least one junction is necessary"):
        check_network(wn)


def test_check_network_no_tanks_or_reservoirs():
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("j1")
    wn.add_junction("j2")
    wn.add_pipe("p1", "j1", "j2")
    with pytest.raises(NetworkModelError, match="At least one tank or reservoir is required"):
        check_network(wn)


def test_check_network_no_links():
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("j1")
    wn.add_junction("j2")
    wn.add_tank("t1")
    with pytest.raises(NetworkModelError, match=r"At least one link \(pipe, pump or valve\) is necessary"):
        check_network(wn)


def test_check_network_orphan_nodes():
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("j1")
    wn.add_junction("j2")
    wn.add_tank("t1")
    wn.add_pipe("p1", "j1", "j2")
    with pytest.raises(NetworkModelError, match="the following nodes are not connected to any links: t1"):
        check_network(wn)


def test_check_network_valid():
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("j1")
    wn.add_junction("j2")
    wn.add_tank("t1")
    wn.add_pipe("p1", "j1", "j2")
    wn.add_pipe("p2", "j2", "t1")
    try:
        check_network(wn)
    except NetworkModelError:
        pytest.fail("check_network raised NetworkModelError unexpectedly!")
