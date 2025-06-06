from unittest.mock import ANY

import pytest
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsProcessingProvider,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt import QtWidgets

import wntrqgis
from wntrqgis.elements import FlowUnit, HeadlossFormula
from wntrqgis.plugin import DurationSettingMenu, SettingMenu
from wntrqgis.settings import ProjectSettings, SettingKey


@pytest.fixture(scope="module")
def load_plugin(qgis_iface):
    # return qgis.utils.loadPlugin("wntrqgis)
    return wntrqgis.classFactory(qgis_iface)


@pytest.fixture(scope="module")
def start_plugin(load_plugin):
    load_plugin.initGui()
    return load_plugin
    # return qgis.utils.startPlugin("wntrqgis")


@pytest.fixture(scope="module")
def processing_provider(qgis_app, start_plugin, scope="module"):
    return qgis_app.processingRegistry().providerById("wntr")


@pytest.fixture(scope="module")
def get_plugin_class(start_plugin):
    return start_plugin
    # return qgis.utils.plugins["wntrqgis"]


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


def list_layers_in_geopackage(geopackage_path):
    layers = QgsVectorLayer(geopackage_path, "geopackage_layers", "ogr")

    assert layers.isValid()

    layer_names = []
    for layer in layers.dataProvider().subLayers():
        layer_name = layer.split("!!::!!")[1]
        layer_names.append(layer_name)

    return layer_names


def test_create_template_geopackage(patched_plugin, mocker, tmp_path):
    geopackage_path = str(tmp_path / "template.gpkg")
    mocker.patch("wntrqgis.plugin.QFileDialog.getSaveFileName", return_value=(geopackage_path, ""))

    patched_plugin.actions["create_template_geopackage"].trigger()

    assert (tmp_path / "template.gpkg").exists()

    layers = ["junctions", "pipes", "pumps", "reservoirs", "tanks", "valves"]
    layers_in_geopackage = list_layers_in_geopackage(str(tmp_path / "template.gpkg"))
    for layer in layers:
        assert layer in layers_in_geopackage


def patch_dialogs(mocker, file, crs):
    mocker.patch("wntrqgis.plugin.QFileDialog", autospec=True).getOpenFileName.return_value = (file, "")

    qpsd = mocker.patch("wntrqgis.plugin.QgsProjectionSelectionDialog", autospec=True)
    qpsd.return_value.exec.return_value = bool(crs)
    qpsd.return_value.crs.return_value = QgsCoordinateReferenceSystem(crs)


@pytest.mark.skipif(not hasattr(QtWidgets.QMessageBox, "Close"), reason="QMessageBox.Close in pytest-qgis will error")
@pytest.mark.qgis_show_map(timeout=3, zoom_to_common_extent=True)
def test_load_inp_file(qgis_iface, patched_plugin, mocker, qgis_new_project):
    patch_dialogs(mocker, wntrqgis.examples["KY10"], "EPSG:32629")

    patched_plugin.actions["load_inp"].trigger()

    assert len(QgsProject.instance().mapLayers()) == 6

    qgis_iface.messageBar.return_value.pushMessage.assert_called_with(
        title="Success",
        text="Loaded .inp file",
        showMore=ANY,
        level=Qgis.MessageLevel.Success,
        duration=ANY,
    )


def test_load_inp_file_bad_inp(qgis_iface, patched_plugin, mocker, bad_inp, qgis_new_project):
    patch_dialogs(mocker, bad_inp, "EPSG:4326")

    patched_plugin.actions["load_inp"].trigger()

    qgis_iface.messageBar.return_value.pushMessage.assert_called_with(
        title="Error",
        text="error reading .inp file: (Error 201) syntax error (%s), at line 330:\n   [FOO]",
        showMore=ANY,
        level=Qgis.MessageLevel.Critical,
        duration=ANY,
    )
    assert len(QgsProject.instance().mapLayers()) == 0


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


@pytest.mark.parametrize("formula", list(HeadlossFormula))
def test_setting_menu_headloss_formula_updates_setting(formula):
    """Test that selecting a headloss formula in SettingMenu updates the project setting."""
    menu = SettingMenu(
        title="Headloss Formula",
        parent=None,
        setting=SettingKey.HEADLOSS_FORMULA,
    )

    action = menu.actions[formula]
    action.trigger()
    assert ProjectSettings().get(SettingKey.HEADLOSS_FORMULA) == formula


@pytest.mark.parametrize("unit", list(FlowUnit))
def test_setting_menu_flow_units_updates_setting(unit):
    """Test that selecting a flow unit in SettingMenu updates the project setting."""
    menu = SettingMenu(
        title="Units",
        parent=None,
        setting=SettingKey.FLOW_UNITS,
    )
    action = menu.actions[unit]
    action.trigger()
    assert ProjectSettings().get(SettingKey.FLOW_UNITS) == unit


def test_setting_menu_checkmarks_reflect_setting(qgis_iface):
    """Test that the checked action matches the current setting."""
    menu = SettingMenu(
        title="Headloss Formula",
        parent=None,
        setting=SettingKey.HEADLOSS_FORMULA,
    )
    # Set to each value and check update_checked
    for formula in HeadlossFormula:
        ProjectSettings().set(SettingKey.HEADLOSS_FORMULA, formula)
        menu.update_checked()
        for f, action in menu.actions.items():
            if f == formula:
                assert action.isChecked()
            else:
                assert not action.isChecked()


def test_duration_setting_menu_triggers_and_checkmarks(qgis_iface):
    """Test DurationSettingMenu triggers and checkmarks."""
    menu = DurationSettingMenu(title="Duration")
    # Test single period
    menu.actions[0].trigger()
    assert ProjectSettings().get(SettingKey.SIMULATION_DURATION) == 0
    # Test several hours
    for hour in [1, 5, 10, 24]:
        menu.actions[hour].trigger()
        assert ProjectSettings().get(SettingKey.SIMULATION_DURATION) == hour
        menu.update_checked()
        for h, action in menu.actions.items():
            if h == hour:
                assert action.isChecked()
            else:
                assert not action.isChecked()
    # Test dynamic addition for a duration not in actions
    ProjectSettings().set(SettingKey.SIMULATION_DURATION, 42)
    menu.update_checked()
    assert menu.actions[42].isChecked()
