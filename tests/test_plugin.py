import pytest
import qgis.utils
from qgis.core import Qgis, QgsCoordinateReferenceSystem, QgsProcessingProvider, QgsProject

import wntrqgis


@pytest.fixture(scope="module")
def load_plugin():
    return qgis.utils.loadPlugin("wntrqgis")


@pytest.fixture(scope="module")
def start_plugin(load_plugin):
    return qgis.utils.startPlugin("wntrqgis")


@pytest.fixture(scope="module")
def processing_provider(qgis_app, start_plugin, scope="module"):
    return qgis_app.processingRegistry().providerById("wntr")


@pytest.fixture(scope="module")
def get_plugin_class(start_plugin):
    return qgis.utils.plugins["wntrqgis"]


@pytest.fixture
def patched_plugin(get_plugin_class, mocker):
    mocker.patch.object(get_plugin_class, "TESTING", True)
    return get_plugin_class


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


def patch_dialogs(mocker, file, crs):
    import wntrqgis.plugin

    mocker.patch("wntrqgis.plugin.QFileDialog", autospec=True).getOpenFileName.return_value = (file, "")

    qpsd = mocker.patch("wntrqgis.plugin.QgsProjectionSelectionDialog", autospec=True)
    qpsd.return_value.exec.return_value = bool(crs)
    qpsd.return_value.crs.return_value = QgsCoordinateReferenceSystem(crs)


@pytest.mark.qgis_show_map(timeout=3, zoom_to_common_extent=True)
def test_load_inp_file(qgis_iface, patched_plugin, mocker, qgis_new_project):
    patch_dialogs(mocker, wntrqgis.examples["KY10"], "EPSG:32629")

    patched_plugin.actions["load_inp"].trigger()

    assert len(QgsProject.instance().mapLayers()) == 6

    assert qgis_iface.messageBar().get_messages(Qgis.Success)[-1].startswith("Success:Loaded .inp file")


def test_load_inp_file_bad_inp(qgis_iface, patched_plugin, mocker, bad_inp, qgis_new_project):
    patch_dialogs(mocker, bad_inp, "EPSG:4326")

    patched_plugin.actions["load_inp"].trigger()

    assert (
        qgis_iface.messageBar()
        .get_messages(Qgis.Critical)[-1]
        .startswith("Error:error reading .inp file: (Error 201) syntax error")
    )


def test_load_inp_file_no_file_selected(patched_plugin, mocker, qgis_new_project):
    patch_dialogs(mocker, "", "EPSG:4326")

    patched_plugin.actions["load_inp"].trigger()

    assert len(QgsProject.instance().mapLayers()) == 0


def test_load_inp_file_no_crs_selected(patched_plugin, mocker, qgis_new_project):
    patch_dialogs(mocker, wntrqgis.examples["KY10"], "")

    patched_plugin.actions["load_inp"].trigger()

    assert len(QgsProject.instance().mapLayers()) == 0


def test_load_example(patched_plugin, qgis_new_project):
    patched_plugin.actions["load_example"].trigger()

    assert len(QgsProject.instance().mapLayers()) == 7


def test_run(patched_plugin, qgis_new_project):
    patched_plugin.actions["load_example"].trigger()

    patched_plugin.actions["run_simulation"].trigger()

    assert len(QgsProject.instance().mapLayers()) == 9


def test_processing_provider(processing_provider):
    assert isinstance(processing_provider, QgsProcessingProvider)


def test_processing_provider_icon(processing_provider):
    assert processing_provider.icon()


def test_processing_provider_name(processing_provider):
    assert processing_provider.name() == "WNTR"


def test_processing_provider_id(processing_provider):
    assert processing_provider.id() == "wntr"


@pytest.mark.parametrize("algorithm", ["importinp", "run", "templatelayers"])
def test_processing_alg_loaded(processing_provider, algorithm):
    assert processing_provider.algorithm(algorithm)


def test_algorithm_properties(processing_provider):
    for alg in processing_provider.algorithms():
        assert alg.displayName() is not None
        assert alg.shortHelpString() is not None
        assert alg.icon() is not None
