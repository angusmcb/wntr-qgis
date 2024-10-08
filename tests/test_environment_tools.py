import importlib.util
from pathlib import Path

import pytest
from qgis.core import QgsCoordinateReferenceSystem, QgsProject

import wntrqgis.environment_tools

# def test_plugin_name():
#    assert plugin_name() == "Water Network Tools for Resilience (WNTR) Integration"
from wntrqgis.plugin import Plugin
from wntrqgis.qgis_plugin_tools.tools.resources import plugin_name  # noqa F401


def test_install_wntr():
    wntrqgis.environment_tools.install_wntr()
    assert importlib.util.find_spec("wntrqgis.packages.wntr")
