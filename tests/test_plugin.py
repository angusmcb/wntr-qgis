from pathlib import Path

import pytest
import qgis.utils
from qgis.core import QgsCoordinateReferenceSystem, QgsProject

from wntrqgis.plugin import Plugin
from wntrqgis.qgis_plugin_tools.tools.resources import plugin_name

# def test_plugin_name():
#    assert plugin_name() == "Water Network Tools for Resilience (WNTR) Integration"


def test_start_plugin(qgis_app, qgis_processing, qgis_new_project):
    wntrplugin = Plugin()
    assert wntrplugin


def test_processing_providers(qgis_app, qgis_processing, qgis_new_project):
    assert "wntr" in [provider.id() for provider in qgis_app.processingRegistry().providers()]


@pytest.mark.qgis_show_map(timeout=10, zoom_to_common_extent=True)
def test_alg_import_inp(qgis_processing, qgis_iface, qgis_new_project):
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
