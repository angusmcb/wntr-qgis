import contextlib
from pathlib import Path

import numpy as np
import pytest
from qgis.core import QgsCoordinateReferenceSystem, QgsProcessingFeedback, QgsProject, QgsVectorLayer


# the examples are store in the plugin folder as they are used in the plugin
@pytest.fixture
def example_dir():
    return Path(__file__).parent.parent / "wntrqgis" / "resources" / "examples"


def examples_list():
    return ["ky1.inp", "ky10.inp", "ky17.inp", "Net3.simplified.inp", "valves.inp", "single_pipe_warning.inp"]


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


def test_processing_providers(qgis_app, qgis_processing):
    assert "wntr" in [provider.id() for provider in qgis_app.processingRegistry().providers()]


@pytest.mark.parametrize("filetype", ["TEMPORARY_OUTPUT", "gpkg", "geojson"])
def test_alg_template_layers(qgis_processing, qgis_iface, qgis_new_project, example_dir, tmp_path, filetype):
    from qgis import processing

    fileset = output_params(expected_model_layers, tmp_path, filetype)

    result = processing.run("wntr:templatelayers", {"CRS": QgsCoordinateReferenceSystem("EPSG:4326"), **fileset})

    assert all(outkey in expected_model_layers for outkey in result)
    QgsProject.instance().addMapLayers(
        [QgsVectorLayer(r) for r in result.values() if isinstance(r, str)]
        + [r for r in result.values() if isinstance(r, QgsVectorLayer)]
    )


@pytest.mark.qgis_show_map(timeout=5, zoom_to_common_extent=True)
def test_alg_import_inp_show_map(qgis_processing, qgis_iface, qgis_new_project, example_dir):
    from qgis import processing

    result = processing.run(
        "wntr:importinp",
        {
            "CRS": QgsCoordinateReferenceSystem("EPSG:32629"),
            "INPUT": str(example_dir / "ky1.inp"),
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
    qgis_processing,
    qgis_iface,
    qgis_new_project,
    example_dir,
    example_name,
):
    from qgis import processing

    expectedoutputs = ["JUNCTIONS", "PUMPS", "PIPES", "RESERVOIRS", "TANKS", "VALVES"]

    result = processing.run(
        "wntr:importinp",
        {
            "CRS": "EPSG:32629",
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


def test_alg_import_inp_and_load_result(qgis_processing, qgis_iface, qgis_new_project):
    from qgis import processing

    # note this doesn't really work to actually load results, but should test style loader doesn't have errors

    with contextlib.suppress(AttributeError):
        processing.runAndLoadResults(
            "wntr:importinp",
            {
                "CRS": "EPSG:32629",
                "INPUT": str(
                    Path(__file__).parent.parent / "wntrqgis" / "resources" / "examples" / "Net3.simplified.inp"
                ),
                "JUNCTIONS": "TEMPORARY_OUTPUT",
                "PIPES": "TEMPORARY_OUTPUT",
                "PUMPS": "TEMPORARY_OUTPUT",
                "RESERVOIRS": "TEMPORARY_OUTPUT",
                "TANKS": "TEMPORARY_OUTPUT",
                "VALVES": "TEMPORARY_OUTPUT",
            },
        )


def test_run_logger(qgis_processing, qgis_new_project, example_dir, tmp_path):
    """todo: add test to feedback from processing"""
    from qgis import processing

    class TestFeedback(QgsProcessingFeedback):
        warningreceived = False

        def pushWarning(self, msg):  # noqa: N802
            self.warningreceived = True

    feedbacktest = TestFeedback()

    inputinp = str(example_dir / "single_pipe_warning.inp")

    fileset = output_params(expected_model_layers, tmp_path, "TEMPORARY_OUTPUT")
    units = 0
    inp_result = processing.run(
        "wntr:importinp",
        {
            "CRS": "EPSG:3089",
            "INPUT": inputinp,
            "UNITS": units,
            **fileset,
        },
    )

    assert all(outkey in expected_model_layers for outkey in inp_result)

    processing.run(
        "wntr:run",
        {
            "OUTPUTNODES": "TEMPORARY_OUTPUT",
            "OUTPUTLINKS": "TEMPORARY_OUTPUT",
            "OUTPUTINP": "TEMPORARY_OUTPUT",
            "UNITS": units,
            "HEADLOSS_FORMULA": 0,
            "DURATION": 0,
            **inp_result,
        },
        feedback=feedbacktest,
    )
    assert feedbacktest.warningreceived


@pytest.mark.parametrize("filetype", ["TEMPORARY_OUTPUT", "gpkg", "geojson", "shp"])
@pytest.mark.parametrize("example", [("Net3.simplified.inp", 24), ("valves.inp", 0)])
def test_alg_chain_inp_run(qgis_processing, qgis_iface, qgis_new_project, example_dir, tmp_path, filetype, example):
    import wntr
    from qgis import processing

    inputinp = str(example_dir / example[0])

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
            "HEADLOSS_FORMULA": 0,
            "DURATION": example[1],
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

    print("***Original results***")  # noqa
    print(inputresults.link["headloss"])  # noqa
    print("***Final results***")  # noqa
    print(outputresults.link["headloss"])  # noqa

    for i in ["demand", "head", "pressure"]:
        assert all(
            all(sublist) for sublist in np.isclose(inputresults.node[i], outputresults.node[i], rtol=0.005)
        ), f" when testing {i}"
    for i in ["flowrate", "headloss", "velocity"]:
        assert all(
            all(sublist)
            for sublist in np.isclose(
                inputresults.link[i],
                outputresults.link[i],
                rtol=0.005,
                atol=1e-04,
            )
        ), f" when testing {i}"


def test_settings(qgis_processing, qgis_new_project, example_dir, tmp_path):
    """todo: add test to feedback from processing"""

    from qgis import processing

    from wntrqgis.wntrqgis_processing.settings import SettingsAlgorithm

    inputinp = str(example_dir / "valves.inp")

    fileset = output_params(expected_model_layers, tmp_path, "TEMPORARY_OUTPUT")
    units = 0
    processing.run(
        SettingsAlgorithm(),
        {
            "CRS": "32637",
            "INPUT": inputinp,
            "UNITS": units,
            **fileset,
        },
    )
