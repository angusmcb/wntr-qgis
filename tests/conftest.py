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
from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True, scope="session")
def patch_iface(qgis_app, qgis_iface):
    qgis_iface.statusBarIface = Mock()
    qgis_iface.layerTreeView = Mock()
    qgis_iface.layerTreeView.return_value.indicators.return_value = []
    qgis_iface.addToolBarWidget = Mock()


@pytest.fixture(autouse=True, scope="session")
def processing(qgis_processing):
    import processing

    return processing


@pytest.fixture(autouse=True, scope="session")
def check_wntr():
    from wntrqgis.dependency_management import WntrInstaller

    try:
        import wntr  # noqa F401
    except ImportError:
        WntrInstaller.install_wntr()


@pytest.fixture
def test_inp_dir():
    return Path(__file__).parent / "test_inps"


@pytest.fixture
def bad_inp(test_inp_dir):
    return str(test_inp_dir / "bad_syntax.inp")


@pytest.fixture
def get_example():
    def _(file_name: str):
        return str(Path(__file__).parent.parent / "wntrqgis" / "resources" / "examples" / file_name)

    return _
