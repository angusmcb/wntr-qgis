import pytest
import wntr
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
)

import wntrqgis


@pytest.fixture
def wn():
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("J1", base_demand=0.01, elevation=10, coordinates=(1, 1))
    wn.add_junction("J2", base_demand=0.02, elevation=20, coordinates=(2, 2))
    wn.add_pipe("P1", "J1", "J2", length=100, diameter=0.3, roughness=100)
    return wn


def test_empty_wn(qgis_new_project):
    wn = wntr.network.WaterNetworkModel()
    layers = wntrqgis.to_qgis(wn)
    assert isinstance(layers, dict)
    assert isinstance(layers["JUNCTIONS"], QgsVectorLayer)


def test_valid_crs_string(wn):
    crs = "EPSG:3857"
    layers = wntrqgis.to_qgis(wn, crs=crs)
    assert isinstance(layers, dict)
    assert "JUNCTIONS" in layers
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
