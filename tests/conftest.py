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

import pytest

from wntrqgis.wntrqgis_processing.provider import Provider


@pytest.fixture(autouse=True, scope="session")
def plugin_provider(qgis_app, qgis_processing):
    provider = Provider()

    qgis_app.processingRegistry().addProvider(provider)

    # test_scripts_path = Path(__file__).parent / "scripts"
    # scripts_paths = ProcessingConfig.getSetting(RUtils.RSCRIPTS_FOLDER) + ";" + test_scripts_path.as_posix()

    # ProcessingConfig.setSettingValue(RUtils.RSCRIPTS_FOLDER, scripts_paths)

    provider.loadAlgorithms()

    return provider


@pytest.fixture
def get_example():
    def _(file_name: str):
        return str(Path(__file__).parent.parent / "wntrqgis" / "resources" / "examples" / file_name)

    return _
