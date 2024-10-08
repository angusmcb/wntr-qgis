from pathlib import Path

import pytest
from qgis.core import QgsCoordinateReferenceSystem, QgsProject

from wntrqgis.plugin import Plugin
from wntrqgis.qgis_plugin_tools.tools.resources import plugin_name  # noqa F401

# def test_plugin_name():
#    assert plugin_name() == "Water Network Tools for Resilience (WNTR) Integration"


def test_start_plugin(qgis_app, qgis_processing, qgis_new_project):  # noqa ARG001
    wntrplugin = Plugin()
    assert wntrplugin


def test_install_wntr():
    newplugin = Plugin()
    assert newplugin._install_wntr()  # noqa SLF001


def test_processing_providers(qgis_app, qgis_processing, qgis_new_project):  # noqa ARG001
    assert "wntr" in [provider.id() for provider in qgis_app.processingRegistry().providers()]


@pytest.mark.qgis_show_map(timeout=10, zoom_to_common_extent=True)
def test_alg_import_inp(qgis_processing, qgis_iface, qgis_new_project):  # noqa ARG001
    from qgis import processing

    result = processing.run(
        "wntr:importinp",
        {
            "CRS": QgsCoordinateReferenceSystem("EPSG:32629"),
            "INPUT": str(Path(__file__).parent.parent / "wntrqgis" / "resources" / "examples" / "Net3.inp"),
            "JUNCTIONS": "TEMPORARY_OUTPUT",
            "PIPES": "TEMPORARY_OUTPUT",
            "PUMPS": "TEMPORARY_OUTPUT",
            "RESERVOIRS": "TEMPORARY_OUTPUT",
            "TANKS": "TEMPORARY_OUTPUT",
            "VALVES": "TEMPORARY_OUTPUT",
        },
    )

    assert "JUNCTIONS" in result
    QgsProject.instance().addMapLayer(result["JUNCTIONS"])
