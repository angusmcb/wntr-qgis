import pytest
import qgis.utils
from qgis.core import QgsCoordinateReferenceSystem, QgsProject

import wntrqgis


@pytest.fixture
def load_plugin():
    return qgis.utils.loadPlugin("wntrqgis")


@pytest.fixture
def start_plugin(load_plugin):
    return qgis.utils.startPlugin("wntrqgis")


@pytest.fixture
def processing_provider(qgis_app, start_plugin):
    return qgis_app.processingRegistry().providerById("wntr")


@pytest.fixture
def get_plugin_class(start_plugin):
    return qgis.utils.plugins["wntrqgis"]


@pytest.fixture
def patched_plugin(get_plugin_class, mocker):
    mocker.patch.object(get_plugin_class, "testing_wait_finished", True)
    return get_plugin_class


@pytest.fixture(params=wntrqgis.examples.values())
def patch_file_crs_dialog(mocker, request):
    open_dialog = mocker.patch("wntrqgis.plugin.QFileDialog", autospec=True)
    open_dialog.getOpenFileName.return_value = (request.param, "")

    projection_dialog = mocker.patch("wntrqgis.plugin.QgsProjectionSelectionDialog", autospec=True)
    projection_dialog.exec.return_value = QgsCoordinateReferenceSystem("EPSG:4326")


def test_load_plugin(load_plugin):
    assert load_plugin


def test_start_plugin(start_plugin):
    assert start_plugin


def test_plugin_class(get_plugin_class):
    import wntrqgis.plugin

    assert isinstance(get_plugin_class, wntrqgis.plugin.Plugin)


def test_create_template_layers(patched_plugin, qgis_new_project):
    patched_plugin.actions["template_layers"].trigger()
    assert len(QgsProject.instance().mapLayers()) == 6


def test_load_inp_file(patched_plugin, patch_file_crs_dialog, qgis_new_project):
    patched_plugin.actions["load_inp"].trigger()

    assert len(QgsProject.instance().mapLayers()) == 6


def test_load_example(patched_plugin, qgis_new_project):
    patched_plugin.actions["load_example"].trigger()

    assert len(QgsProject.instance().mapLayers()) == 7


def test_processing_provider(processing_provider):
    from qgis.core import QgsProcessingProvider

    assert isinstance(processing_provider, QgsProcessingProvider)


def test_processing_provider_icon(processing_provider):
    assert processing_provider.icon()


def test_processing_provider_name(processing_provider):
    assert processing_provider.name() == "WNTR"


@pytest.mark.parametrize("algorithm", ["importinp", "run", "templatelayers"])
def test_processing_alg_loaded(processing_provider, algorithm):
    assert processing_provider.algorithm(algorithm)


def test_algorithm_properties(processing_provider):
    for alg in processing_provider.algorithms():
        assert alg.displayName() is not None
        assert alg.shortHelpString() is not None
        assert alg.icon() is not None
