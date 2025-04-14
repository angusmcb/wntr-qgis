import pytest
from qgis.core import NULL, QgsCoordinateReferenceSystem, QgsProject, QgsVectorLayer

import wntrqgis


@pytest.fixture
def wn():
    import wntr

    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("J1", base_demand=0.01, elevation=10, coordinates=(1, 1))
    wn.add_junction("J2", base_demand=0.02, elevation=20, coordinates=(2, 2))
    wn.add_reservoir("R1", base_head=10, coordinates=(0, 0))
    wn.add_pipe("P1", "J1", "J2", length=100, diameter=0.3, roughness=100)
    wn.add_pipe("P2", "J2", "R1", length=150, diameter=400, roughness=100)
    return wn


@pytest.fixture
def eps(wn):
    wn.options.time.duration = 3600


@pytest.fixture
def results(wn):
    import wntr

    sim = wntr.sim.EpanetSimulator(wn)
    return sim.run_sim()


def check_values(layer, field_name, expected_values):
    """
    Helper function to check if the values in a specific field of a layer's features match the expected values.

    :param layer: QgsVectorLayer to check.
    :param field_name: Name of the field to validate.
    :param expected_values: List of expected values.
    :raises AssertionError: If the field values do not match the expected values.
    """
    assert layer.isValid(), "Layer is not valid."
    assert layer.fields().indexFromName(field_name) != -1, f"Field '{field_name}' does not exist in the layer."

    actual_values = [feature[field_name] for feature in layer.getFeatures()]

    error_message = f"Field '{field_name}' values do not match. Expected: {expected_values}, Actual: {actual_values}"
    assert actual_values == expected_values, error_message


def test_basic_wn(qgis_new_project, wn):
    layers = wntrqgis.to_qgis(wn)
    assert isinstance(layers, dict)
    assert isinstance(layers["JUNCTIONS"], QgsVectorLayer)
    assert isinstance(layers["PIPES"], QgsVectorLayer)
    assert len(QgsProject.instance().mapLayers()) == 6
    check_values(layers["JUNCTIONS"], "name", ["J1", "J2"])


def test_empty_wn(qgis_new_project):
    import wntr

    wn = wntr.network.WaterNetworkModel()
    layers = wntrqgis.to_qgis(wn)
    assert isinstance(layers, dict)
    assert isinstance(layers["JUNCTIONS"], QgsVectorLayer)
    assert len(QgsProject.instance().mapLayers()) == 6
    assert layers["JUNCTIONS"].featureCount() == 0


def test_demand_conversion(wn):
    layers = wntrqgis.to_qgis(wn, units="LPS")

    check_values(layers["JUNCTIONS"], "base_demand", [10, 20])


def test_results(qgis_new_project, wn, results):
    layers = wntrqgis.to_qgis(wn, results=results, units="LPS")
    assert len(QgsProject.instance().mapLayers()) == 2
    check_values(layers["NODES"], "demand", [10.0, 20.0, -30.0])
    check_values(layers["LINKS"], "flowrate", [-10.0, -30.0])


def test_eps_results(qgis_new_project, wn, eps, results):
    layers = wntrqgis.to_qgis(wn, results=results, units="LPS")
    assert len(QgsProject.instance().mapLayers()) == 2
    check_values(layers["NODES"], "demand", [[10.0, 10.0], [20.0, 20.0], [-30.0, -30.0]])
    check_values(layers["LINKS"], "flowrate", [[-10.0, -10.0], [-30.0, -30.0]])


def test_custom_attr_str(wn):
    wn.nodes["J1"].custom_str = "Custom String"
    layers = wntrqgis.to_qgis(wn)

    check_values(layers["JUNCTIONS"], "custom_str", ["Custom String", NULL])


def test_custom_attr_int(wn):
    wn.nodes["J2"].custom_int = 42
    layers = wntrqgis.to_qgis(wn)

    check_values(layers["JUNCTIONS"], "custom_int", [NULL, 42])


def test_custom_attr_float(wn):
    wn.nodes["J1"].custom_float = 3.14
    layers = wntrqgis.to_qgis(wn)

    check_values(layers["JUNCTIONS"], "custom_float", [3.14, NULL])


def test_custom_attr_bool(wn):
    wn.links["P1"].custom_bool = True
    layers = wntrqgis.to_qgis(wn)

    check_values(layers["PIPES"], "custom_bool", [True, NULL])


def test_valid_crs_string(wn):
    crs = "EPSG:3857"
    layers = wntrqgis.to_qgis(wn, crs=crs)

    assert layers["JUNCTIONS"].crs().authid() == crs


def test_valid_crs_object(wn):
    crs = QgsCoordinateReferenceSystem("EPSG:3857")
    layers = wntrqgis.to_qgis(wn, crs=crs)
    assert isinstance(layers, dict)
    assert "JUNCTIONS" in layers
    assert layers["JUNCTIONS"].crs().authid() == crs.authid()


def test_invalid_crs_string(wn):
    crs = "INVALID_CRS"
    with pytest.raises(ValueError, match=f"CRS {crs} is not valid."):
        wntrqgis.to_qgis(wn, crs=crs)


def test_invalid_crs_object(wn):
    crs = QgsCoordinateReferenceSystem("INVALID_CRS")
    with pytest.raises(ValueError, match="is not valid."):
        wntrqgis.to_qgis(wn, crs=crs)


def test_default_crs(wn):
    layers = wntrqgis.to_qgis(wn)
    assert isinstance(layers, dict)
    assert "JUNCTIONS" in layers
    assert layers["JUNCTIONS"].crs().isValid() is False


def test_no_crs(wn):
    layers = wntrqgis.to_qgis(wn, crs=None)
    assert isinstance(layers, dict)
    assert "JUNCTIONS" in layers
    assert layers["JUNCTIONS"].crs().isValid() is False
