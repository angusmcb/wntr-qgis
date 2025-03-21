"""
This class contains fixtures and common helper function to keep the test files
shorter.

pytest-qgis (https://pypi.org/project/pytest-qgis) contains the following helpful
fixtures:

* qgis_app initializes and returns fully configured QgsApplication.
  This fixture is called automatically on the start of pytest session.
* qgis_canvas initializes and returns QgsMapCanvas
* qgis_iface returns mocked QgsInterface
* new_project makes sure that all the map layers and configurations are removed.
  This should be used with tests that add stuff to QgsProject.

"""

from pathlib import Path

import geopandas as gpd
import pytest
from qgis.core import QgsVectorLayer

from wntrqgis.dependency_management import WqDependencyManagement


@pytest.fixture(autouse=True)
def patch_iface(qgis_iface, qgis_processing, mocker):
    import processing

    import wntrqgis.plugin

    mocker.patch.object(wntrqgis.plugin.iface, "statusBarIface", create=True)
    mocker.patch.object(processing.gui.Postprocessing.iface, "layerTreeView", create=True)


@pytest.fixture(autouse=True, scope="session")
def setup_processing(qgis_processing):
    pass


@pytest.fixture
def get_example():
    def _(file_name: str):
        return str(Path(__file__).parent.parent / "wntrqgis" / "resources" / "examples" / file_name)

    return _


def test_model_layer(file_name):
    return str(Path(__file__).parent / "test_models" / file_name)


@pytest.fixture
def flegere_layers():
    junctions = QgsVectorLayer(test_model_layer("la-praz-junction.geojson"), "", "ogr")
    reservoirs = QgsVectorLayer(test_model_layer("flegere-reservoir.geojson"), "", "ogr")
    pipes = QgsVectorLayer(test_model_layer("flegere-lift.geojson"), "", "ogr")
    tank = QgsVectorLayer(test_model_layer("flegere-tank.geojson"), "", "ogr")

    return {"junctions": junctions, "reservoirs": reservoirs, "pipes": pipes, "tanks": tank}


@pytest.fixture
def flegere_gdfs():
    files = {
        "junctions": "la-praz-junction.geojson",
        "reservoirs": "flegere-reservoir.geojson",
        "pipes": "flegere-lift.geojson",
        "tanks": "flegere-tank.geojson",
    }

    return {k: gpd.read_file(test_model_layer(v)) for k, v in files.items()}


WqDependencyManagement.ensure_wntr()
