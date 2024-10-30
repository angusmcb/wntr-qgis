import contextlib
from pathlib import Path

import numpy as np
import pytest
from qgis.core import QgsCoordinateReferenceSystem, QgsProject, QgsVectorLayer

# def test_plugin_name():
#    assert plugin_name() == "Water Network Tools for Resilience (WNTR) Integration"
# from wntrqgis.dependency_management import WqDependencyManagemet
from wntrqgis.plugin import Plugin
from wntrqgis.qgis_plugin_tools.tools.resources import plugin_name  # noqa F401

# WqDependencyManagemet.install_wntr()


def test_start_plugin(qgis_app, qgis_processing, qgis_new_project):  # noqa ARG001
    wntrplugin = Plugin()
    assert wntrplugin


# the examples are store in the plugin folder as they are used in the plugin
@pytest.fixture
def example_dir():
    return Path(__file__).parent.parent / "wntrqgis" / "resources" / "examples"


def examples_list():
    return ["Net1.inp", "Net2.inp", "Net3.inp", "Net6.inp", "ky10.inp"]


expected_model_layers = ["JUNCTIONS", "PUMPS", "PIPES", "RESERVOIRS", "TANKS", "VALVES"]


def output_params(params, tmp_path, filetype="TEMPORARY_OUTPUT"):
    outputfilesets = {
        "TEMPORARY_OUTPUT": {lyr: "TEMPORARY_OUTPUT" for lyr in params},
        "gpkg": {
            lyr: "ogr:dbname='" + str(tmp_path / "outputs.gpkg") + "' table=\"" + lyr + '" (geom)' for lyr in params
        },
        "shp": {lyr: str(tmp_path / (lyr + ".shp")) for lyr in params},
        "geojson": {lyr: str(tmp_path / (lyr + ".geojson")) for lyr in params},
    }
    return outputfilesets[filetype]


def test_processing_providers(qgis_app, qgis_processing):  # noqa ARG001
    assert "wntr" in [provider.id() for provider in qgis_app.processingRegistry().providers()]


@pytest.mark.parametrize("filetype", ["TEMPORARY_OUTPUT", "gpkg", "geojson"])
def test_alg_template_layers(qgis_processing, qgis_iface, qgis_new_project, example_dir, tmp_path, filetype):  # noqa ARG001
    from qgis import processing

    fileset = output_params(expected_model_layers, tmp_path, filetype)

    result = processing.run("wntr:templatelayers", {"CRS": QgsCoordinateReferenceSystem("EPSG:4326"), **fileset})

    assert all(outkey in expected_model_layers for outkey in result)
    QgsProject.instance().addMapLayers(
        [QgsVectorLayer(r) for r in result.values() if isinstance(r, str)]
        + [r for r in result.values() if isinstance(r, QgsVectorLayer)]
    )


@pytest.mark.qgis_show_map(timeout=5, zoom_to_common_extent=True)
def test_alg_import_inp_show_map(qgis_processing, qgis_iface, qgis_new_project, example_dir):  # noqa ARG001
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


@pytest.mark.parametrize("example_name", examples_list())
def test_alg_import_inp_all_examples(
    qgis_processing,  # noqa: ARG001
    qgis_iface,  # noqa: ARG001
    qgis_new_project,  # noqa: ARG001
    example_dir,
    example_name,
):
    from qgis import processing

    expectedoutputs = ["JUNCTIONS", "PUMPS", "PIPES", "RESERVOIRS", "TANKS", "VALVES"]

    result = processing.run(
        "wntr:importinp",
        {
            "CRS": QgsCoordinateReferenceSystem("EPSG:32629"),
            "INPUT": str(example_dir / example_name),
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


@pytest.mark.parametrize("filetype", ["TEMPORARY_OUTPUT", "gpkg", "geojson", "shp"])
def test_alg_chain_inp_run(qgis_processing, qgis_iface, qgis_new_project, example_dir, tmp_path, filetype):  # noqa ARG001
    import wntr
    from qgis import processing

    inputinp = str(example_dir / "Net3.simplified.inp")

    fileset = output_params(expected_model_layers, tmp_path, filetype)
    units = 0
    inp_result = processing.run(
        "wntr:importinp",
        {
            "CRS": QgsCoordinateReferenceSystem("EPSG:32629"),
            "INPUT": inputinp,
            "UNITS": units,
            **fileset,
        },
    )

    assert all(outkey in expected_model_layers for outkey in inp_result)

    run_result = processing.run(
        "wntr:run",
        {
            "OUTPUTNODES": "TEMPORARY_OUTPUT",
            "OUTPUTLINKS": "TEMPORARY_OUTPUT",
            "OUTPUTINP": "TEMPORARY_OUTPUT",
            "UNITS": units,
            **inp_result,
        },
    )

    expected_run_results = ["OUTPUTNODES", "OUTPUTLINKS", "OUTPUTINP"]
    assert all(outkey in expected_run_results for outkey in run_result)

    inputwn = wntr.network.read_inpfile(inputinp)
    sim = wntr.sim.EpanetSimulator(inputwn)
    inputresults = sim.run_sim()

    wn = wntr.network.read_inpfile(run_result["OUTPUTINP"])
    sim = wntr.sim.EpanetSimulator(wn)
    outputresults = sim.run_sim()

    for i in ["demand", "head", "pressure"]:
        assert all(all(sublist) for sublist in np.isclose(inputresults.node[i], outputresults.node[i]))
    for i in ["flowrate", "headloss", "velocity"]:
        assert all(all(sublist) for sublist in np.isclose(inputresults.link[i], outputresults.link[i]))
