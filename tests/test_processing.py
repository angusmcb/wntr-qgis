from pathlib import Path

import numpy as np
import pytest
from qgis.core import QgsCoordinateReferenceSystem, QgsProcessingFeedback, QgsProject, QgsVectorLayer

from wntrqgis.wntrqgis_processing.empty_model import TemplateLayers
from wntrqgis.wntrqgis_processing.import_inp import ImportInp
from wntrqgis.wntrqgis_processing.run_simulation import RunSimulation
from wntrqgis.wntrqgis_processing.settings import SettingsAlgorithm


# the examples are store in the plugin folder as they are used in the plugin
@pytest.fixture
def example_dir():
    return Path(__file__).parent.parent / "wntrqgis" / "resources" / "examples"


@pytest.fixture
def template_alg():
    return TemplateLayers().create()


@pytest.fixture
def import_alg():
    return ImportInp().create()


@pytest.fixture
def run_alg():
    return RunSimulation().create()


@pytest.fixture
def template_alg_params():
    return {
        "CRS": QgsCoordinateReferenceSystem("EPSG:32629"),
        "JUNCTIONS": "TEMPORARY_OUTPUT",
        "PIPES": "TEMPORARY_OUTPUT",
        "PUMPS": "TEMPORARY_OUTPUT",
        "RESERVOIRS": "TEMPORARY_OUTPUT",
        "TANKS": "TEMPORARY_OUTPUT",
        "VALVES": "TEMPORARY_OUTPUT",
    }


@pytest.fixture
def import_alg_params(example_dir, template_alg_params):
    template_alg_params["INPUT"] = str(example_dir / "ky1.inp")
    return template_alg_params


@pytest.fixture(
    params=["ky1.inp", "ky10.inp", "ky17.inp", "Net3.simplified.inp", "valves.inp", "single_pipe_warning.inp"]
)
def test_inp(import_alg_params, example_dir, request):
    file = str(example_dir / request.param)
    import_alg_params["INPUT"] = file
    return file


@pytest.fixture(params=["TEMPORARY_OUTPUT", "gpkg", "geojson", "shp"])
def file_type(template_alg_params, tmp_path, request):
    file_type = request.param
    template_alg_params.update(output_params(model_layers, tmp_path, file_type))
    return file_type


model_layers = ["JUNCTIONS", "PUMPS", "PIPES", "RESERVOIRS", "TANKS", "VALVES"]


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


def test_alg_template_layers(processing, qgis_new_project, template_alg, template_alg_params):
    result = processing.runAndLoadResults(template_alg, template_alg_params)

    assert all(outkey in model_layers for outkey in result)


@pytest.mark.qgis_show_map(timeout=3, zoom_to_common_extent=True)
def test_alg_import_inp_show_map(processing, import_alg, import_alg_params, qgis_new_project):
    result = processing.runAndLoadResults(import_alg, import_alg_params)

    assert all(outkey in model_layers for outkey in result)


def test_alg_import_inp_all_examples(processing, import_alg, import_alg_params, qgis_new_project, test_inp):
    result = processing.runAndLoadResults(import_alg, import_alg_params)

    assert all(outkey in model_layers for outkey in result)


@pytest.mark.filterwarnings("ignore: 1 pipes have very different attribute length")
def test_run_logger(processing, import_alg, run_alg, import_alg_params, qgis_new_project, example_dir):
    """todo: add test to feedback from processing"""

    class TestFeedback(QgsProcessingFeedback):
        warningreceived = False

        def pushWarning(self, msg):  # noqa: N802
            self.warningreceived = True

    feedbacktest = TestFeedback()

    import_alg_params["INPUT"] = str(example_dir / "single_pipe_warning.inp")
    import_alg_params["UNITS"] = 0

    inp_result = processing.run(import_alg, import_alg_params)

    processing.run(
        run_alg,
        {
            "OUTPUTNODES": "TEMPORARY_OUTPUT",
            "OUTPUTLINKS": "TEMPORARY_OUTPUT",
            "OUTPUTINP": "TEMPORARY_OUTPUT",
            "UNITS": 0,
            "HEADLOSS_FORMULA": 0,
            "DURATION": 0,
            **inp_result,
        },
        feedback=feedbacktest,
    )
    assert feedbacktest.warningreceived


@pytest.mark.filterwarnings("ignore: 110 pipes have very different attribute length")
@pytest.mark.parametrize(("example", "duration"), [("Net3.simplified.inp", 24), ("valves.inp", 0)])
def test_alg_chain_inp_run(
    processing,
    qgis_new_project,
    example_dir,
    run_alg,
    import_alg,
    import_alg_params,
    file_type,
    example,
    duration,
):
    import wntr

    inputinp = str(example_dir / example)

    import_alg_params["UNITS"] = 0
    import_alg_params["INPUT"] = inputinp

    inp_result = processing.run(import_alg, import_alg_params)

    run_result = processing.run(
        run_alg,
        {
            "OUTPUTNODES": "TEMPORARY_OUTPUT",
            "OUTPUTLINKS": "TEMPORARY_OUTPUT",
            "OUTPUTINP": "TEMPORARY_OUTPUT",
            "UNITS": 0,
            "HEADLOSS_FORMULA": 0,
            "DURATION": duration,
            **inp_result,
        },
    )

    expected_run_results = ["OUTPUTNODES", "OUTPUTLINKS", "OUTPUTINP"]
    assert all(outkey in expected_run_results for outkey in run_result)

    inputwn = wntr.network.read_inpfile(inputinp)
    inputresults = wntr.sim.EpanetSimulator(inputwn).run_sim()

    wn = wntr.network.read_inpfile(run_result["OUTPUTINP"])
    outputresults = wntr.sim.EpanetSimulator(wn).run_sim()

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


def test_settings(processing, qgis_new_project, example_dir, tmp_path):
    """todo: add test to feedback from processing"""

    # inputinp = str(example_dir / "valves.inp")

    # fileset = output_params(model_layers, tmp_path, "TEMPORARY_OUTPUT")
    # units = 0
    # processing.run(
    #     SettingsAlgorithm().create(),
    #     {
    #         "CRS": "32637",
    #         "INPUT": inputinp,
    #         "UNITS": units,
    #         **fileset,
    #     },
    # )
