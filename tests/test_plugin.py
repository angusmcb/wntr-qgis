import contextlib
from pathlib import Path

import pytest
from qgis.core import QgsCoordinateReferenceSystem, QgsProject

# def test_plugin_name():
#    assert plugin_name() == "Water Network Tools for Resilience (WNTR) Integration"
import wntrqgis.environment_tools

# from wntrqgis.plugin import Plugin
from wntrqgis.qgis_plugin_tools.tools.resources import plugin_name  # noqa F401

wntrqgis.environment_tools.install_wntr()


# def test_start_plugin(qgis_app, qgis_processing, qgis_new_project):
#    wntrplugin = Plugin()
#    assert wntrplugin


# the examples are store in the plugin folder as they are used in the plugin
@pytest.fixture
def example_dir():
    return Path(__file__).parent.parent / "wntrqgis" / "resources" / "examples"


@pytest.fixture
def examples_list():
    return ["Net1.inp", "Net2.inp", "Net3.inp"]


def test_processing_providers(qgis_app, qgis_processing):  # noqa ARG001
    assert "wntr" in [provider.id() for provider in qgis_app.processingRegistry().providers()]


def test_alg_empty_model(qgis_processing, qgis_iface, qgis_new_project):  # noqa ARG001
    from qgis import processing

    result = processing.run(
        "wntr:emptymodel",
        {
            "CRS": QgsCoordinateReferenceSystem("EPSG:4326"),
            "JUNCTIONS": "TEMPORARY_OUTPUT",
            "PIPES": "TEMPORARY_OUTPUT",
            "PUMPS": "TEMPORARY_OUTPUT",
            "RESERVOIRS": "TEMPORARY_OUTPUT",
            "TANKS": "TEMPORARY_OUTPUT",
            "VALVES": "TEMPORARY_OUTPUT",
        },
    )

    expectedoutputs = ["JUNCTIONS", "PUMPS", "PIPES", "RESERVOIRS", "TANKS", "VALVES"]
    assert all(outkey in expectedoutputs for outkey in result)
    QgsProject.instance().addMapLayers(result.values())


@pytest.mark.qgis_show_map(timeout=5, zoom_to_common_extent=True)
def test_alg_import_inp(qgis_processing, qgis_iface, qgis_new_project, example_dir):  # noqa ARG001
    from qgis import processing

    result = processing.run(
        "wntr:importinp",
        {
            "CRS": QgsCoordinateReferenceSystem("EPSG:32629"),
            "INPUT": str(example_dir / "Net1.inp"),
            "JUNCTIONS": "TEMPORARY_OUTPUT",
            "PIPES": "TEMPORARY_OUTPUT",
            "PUMPS": "TEMPORARY_OUTPUT",
            "RESERVOIRS": "TEMPORARY_OUTPUT",
            "TANKS": "TEMPORARY_OUTPUT",
            "VALVES": "TEMPORARY_OUTPUT",
        },
    )

    expectedoutputs = ["JUNCTIONS", "PUMPS", "PIPES", "RESERVOIRS", "TANKS", "VALVES"]
    assert all(outkey in expectedoutputs for outkey in result)
    QgsProject.instance().addMapLayers(result.values())


def test_alg_import_inp_all_examples(qgis_processing, qgis_iface, qgis_new_project, example_dir, examples_list):  # noqa ARG001
    from qgis import processing

    expectedoutputs = ["JUNCTIONS", "PUMPS", "PIPES", "RESERVOIRS", "TANKS", "VALVES"]

    for example in examples_list:
        result = processing.run(
            "wntr:importinp",
            {
                "CRS": QgsCoordinateReferenceSystem("EPSG:32629"),
                "INPUT": str(example_dir / example),
                "JUNCTIONS": "TEMPORARY_OUTPUT",
                "PIPES": "TEMPORARY_OUTPUT",
                "PUMPS": "TEMPORARY_OUTPUT",
                "RESERVOIRS": "TEMPORARY_OUTPUT",
                "TANKS": "TEMPORARY_OUTPUT",
                "VALVES": "TEMPORARY_OUTPUT",
            },
        )
        assert all(outkey in expectedoutputs for outkey in result)


def test_alg_import_inp_and_load_result(qgis_processing, qgis_iface, qgis_new_project):  # noqa ARG001
    from qgis import processing

    # note this doesn't really work to actually load results, but should test style loader doesn't have errors

    with contextlib.suppress(AttributeError):
        processing.runAndLoadResults(
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


@pytest.mark.qgis_show_map(timeout=5, zoom_to_common_extent=True)
def test_alg_chain_inp_run(qgis_processing, qgis_iface, qgis_new_project, tmp_path):  # noqa ARG001
    from qgis import processing

    expected_inp_results = ["JUNCTIONS", "PUMPS", "PIPES", "RESERVOIRS", "TANKS", "VALVES"]
    outputfilesets = {
        "TEMPORARY_OUTPUT": {lyr: "TEMPORARY_OUTPUT" for lyr in expected_inp_results},
        "GPKG": {
            lyr: "ogr:dbname='" + str(tmp_path / "outputs.gpkg") + "' table=\"" + lyr + '" (geom)'
            for lyr in expected_inp_results
        },
        # "shape": {l: str(tmp_path / (l + ".shp")) for l in expected_inp_results},
    }

    for fileset in outputfilesets.values():
        template_result = processing.run(
            "wntr:emptymodel", {"CRS": QgsCoordinateReferenceSystem("EPSG:4326"), **fileset}
        )

        expectedoutputs = ["JUNCTIONS", "PUMPS", "PIPES", "RESERVOIRS", "TANKS", "VALVES"]
        assert all(outkey in expectedoutputs for outkey in template_result)

        inp_result = processing.run(
            "wntr:importinp",
            {
                "CRS": QgsCoordinateReferenceSystem("EPSG:32629"),
                "INPUT": str(Path(__file__).parent.parent / "wntrqgis" / "resources" / "examples" / "Net3.inp"),
                **fileset,
            },
        )

        assert all(outkey in expected_inp_results for outkey in inp_result)

        run_result = processing.run(
            "wntr:run",
            {
                "OUTPUTNODES": "TEMPORARY_OUTPUT",
                "OUTPUTLINKS": "TEMPORARY_OUTPUT",
                **inp_result,
            },
        )

        expected_run_results = ["OUTPUTNODES", "OUTPUTLINKS"]
        assert all(outkey in expected_run_results for outkey in run_result)
    QgsProject.instance().addMapLayers(run_result.values())
