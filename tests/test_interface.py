import pytest
from qgis.core import QgsFields, QgsVectorLayer

import wntrqgis.elements
from wntrqgis.interface import (
    NetworkModelError,
    Writer,
    _Converter,
    _Curves,
    _Patterns,
    check_network,
)


@pytest.fixture
def wn():
    import wntr

    return wntr.network.WaterNetworkModel()


@pytest.fixture
def qgs_layer():
    return QgsVectorLayer("Point", "test_layer", "memory")


def test_patterns_add(wn):
    patterns = _Patterns(wn)
    pattern_name = patterns.add("1 2 3")
    assert pattern_name == "2"


def test_patterns_get(wn):
    patterns = _Patterns(wn)
    pattern_name = patterns.add("1 2 3")
    pattern = patterns.get(pattern_name)
    assert pattern == "1.0 2.0 3.0"


def test_patterns_add_empty(wn):
    patterns = _Patterns(wn)
    pattern_name = patterns.add("")
    assert pattern_name is None


def test_curves_add_one(wn):
    curves = _Curves(wn, _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS))
    curve_name = curves._add_one("[(1,2), (3,4)]", _Curves.Type.HEAD)
    assert curve_name == "1"


def test_curves_get(wn):
    curves = _Curves(wn, _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS))
    curve_name = curves._add_one("[(1,2), (3,4)]", _Curves.Type.HEAD)
    curve = curves.get(curve_name)
    assert curve == "[(1.0, 2.0), (3.0, 4.0)]"


def test_curves_add_invalid(wn):
    curves = _Curves(wn, _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS))
    with pytest.raises(wntrqgis.interface.CurveError):
        curves._add_one(None, _Curves.Type.HEAD)


def test_writer_get_qgsfields(wn):
    writer = Writer(wn)
    fields = writer.get_qgsfields(wntrqgis.elements.ModelLayer.JUNCTIONS)
    assert isinstance(fields, QgsFields)


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
