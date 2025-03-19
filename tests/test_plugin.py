from unittest.mock import patch

import pytest
from qgis.core import QgsCoordinateReferenceSystem, QgsTask
from qgis.PyQt.QtWidgets import QAction

import wntrqgis
import wntrqgis.plugin


@pytest.fixture
def plugin():
    plugin_class = wntrqgis.plugin.Plugin()
    plugin_class.initGui()
    plugin_class.initProcessing()
    return plugin_class


def test_load_plugin(qgis_app, qgis_iface):
    import qgis.utils

    assert qgis.utils.loadPlugin("wntrqgis")


def test_class_factory(qgis_app, qgis_iface):
    from qgis.utils import iface

    plugin_class = wntrqgis.classFactory(iface)

    assert plugin_class
    plugin_class.initGui()


def test_create_template_layers(qgis_app, qgis_iface, qgis_processing, plugin, mocker):
    mocker.patch("wntrqgis.plugin.processing")
    mocker.patch.object(wntrqgis.plugin.iface, "statusBarIface", create=True)
    task = plugin.create_template_layers()
    assert task.waitForFinished()
    assert task.status() == QgsTask.TaskStatus.Complete


@pytest.mark.parametrize("file", wntrqgis.examples.values())
def test_load_inp_file(qgis_app, qgis_iface, qgis_processing, mocker, plugin, file):
    opendialog = mocker.patch("wntrqgis.plugin.QFileDialog", autospec=True)
    opendialog.getOpenFileName.return_value = (file, "")
    projectiondialog = mocker.patch("wntrqgis.plugin.QgsProjectionSelectionDialog", autospec=True)
    projectiondialog.exec.return_value = QgsCoordinateReferenceSystem("EPSG:4326")

    mocker.patch("wntrqgis.plugin.processing")
    mocker.patch.object(wntrqgis.plugin.iface, "statusBarIface", create=True)

    task = plugin.load_inp_file()

    assert task.waitForFinished()
    assert task.status() == QgsTask.TaskStatus.Complete


def test_load_example(qgis_app, qgis_iface, qgis_processing, plugin, mocker):
    mocker.patch("wntrqgis.plugin.processing")
    mocker.patch.object(wntrqgis.plugin.iface, "statusBarIface", create=True)
    task = plugin.load_example()
    assert task.waitForFinished()
    assert task.status() == QgsTask.TaskStatus.Complete


def test_algorithm_properties():
    from wntrqgis.wntrqgis_processing.provider import Provider

    provider = Provider()
    provider.loadAlgorithms()

    for alg in provider.algorithms():
        assert alg.displayName() is not None
        assert alg.shortHelpString() is not None
        assert alg.icon() is not None
