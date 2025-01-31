from pathlib import Path

import geopandas as gpd
import pytest
import wntr
from qgis.core import QgsProject, QgsVectorLayer

import wntrqgis
import wntrqgis as wq
import wntrqgis.elements
from wntrqgis import interface
from wntrqgis.elements import FieldGroup


def to_layers(gdfs: dict[str, gpd.GeoDataFrame]) -> dict[str, QgsVectorLayer]:
    return {key: QgsVectorLayer(gdf.to_json(), str(key), "ogr") for key, gdf in gdfs.items()}


def test_get_field_groups():
    wn = wntr.network.WaterNetworkModel()
    assert interface._get_field_groups(wn) == FieldGroup(0)
    wn.options.quality.parameter = "CHEMICAL"
    wn.options.report.energy = "YES"
    wn.options.hydraulic.demand_model = "PDD"
    assert (
        interface._get_field_groups(wn)
        == FieldGroup.PRESSURE_DEPENDENT_DEMAND | FieldGroup.ENERGY | FieldGroup.WATER_QUALITY_ANALYSIS
    )


def test_examples():
    example = wntrqgis.Example.KY1
    assert isinstance(example, str)
    wntr.network.WaterNetworkModel(example)


def test_to_qgis(qgis_new_project):
    inpfile = wntrqgis.Example.KY1

    wntrqgis.to_qgis(inpfile)


def test_to_qgis_results(qgis_new_project):
    inpfile = wntrqgis.Example.KY1

    wn = wntr.network.WaterNetworkModel(inpfile)

    sim = wntr.sim.EpanetSimulator(wn)
    sim_results = sim.run_sim()

    wntrqgis.to_qgis(wn, sim_results)


@pytest.mark.filterwarnings("ignore: 984 pipes have very different attribute length")
def test_from_qgis(qgis_new_project):
    inpfile = wntrqgis.Example.KY1
    layers = wntrqgis.to_qgis(inpfile)

    del layers[wntrqgis.elements.ModelLayer.VALVES]

    new_wn = wntrqgis.from_qgis(layers, "GPM")

    assert new_wn


def test_empty_wn(qgis_new_project):
    wn = wntr.network.WaterNetworkModel()
    layers = wq.to_qgis(wn)
    assert isinstance(layers, dict)
    assert isinstance(layers["JUNCTIONS"], QgsVectorLayer)


def test_flegere(qgis_new_project, flegere_gdfs):
    flegere_layers = to_layers(flegere_gdfs)
    wn = wq.from_qgis(flegere_layers, "lps")
    layers = wq.to_qgis(wn)
    assert isinstance(layers["JUNCTIONS"], QgsVectorLayer)


def test_flegere_broken_layername(qgis_new_project, flegere_layers):
    flegere_layers["wrongname"] = flegere_layers["junctions"]

    with pytest.raises(ValueError):
        wq.from_qgis(flegere_layers, "LPS")


@pytest.mark.qgis_show_map(timeout=5, zoom_to_common_extent=True)
def test_flegere_snap(qgis_new_project, flegere_layers):
    QgsProject.instance().addMapLayers(flegere_layers.values())

    wn = wq.from_qgis(flegere_layers, "LPS")

    wq.to_qgis(wn)

    wq.interface.check_network(wn)


def test_flegere_naming(flegere_layers):
    wn = wq.from_qgis(flegere_layers, "lps")
    assert wn.node_name_list == ["1", "top_res", "2"]
    assert wn.link_name_list == ["1", "vertex"]


def test_flegere_no_attributes(flegere_gdfs):
    attless_gdfs = {k: gpd.GeoDataFrame(v["geometry"]) for k, v in flegere_gdfs.items()}
    wq.from_qgis(to_layers(attless_gdfs), "lps")


@pytest.mark.parametrize(
    "unit,expected_demand", {("GPM", 6.30901964e-05), ("SI", 1), ("sI", 1), ("LPS", 0.001), ("CFS", 0.0283168466)}
)
def test_flegere_conversion(qgis_new_project, flegere_layers, unit, expected_demand):
    wn = wq.from_qgis(flegere_layers, unit)
    assert wn.get_node("1").base_demand == expected_demand


def test_flegere_bad_units(qgis_new_project, flegere_layers):
    with pytest.raises(
        ValueError,
        match="Units 'NON-EXISTANT' is not a known set of units. Possible units are: LPS, LPM, MLD, CMH, CFS, GPM, MGD, IMGD, AFD, SI",
    ):
        wq.from_qgis(flegere_layers, units="Non-existant")


@pytest.mark.parametrize("unit,expected_length", [("LPS", 100), ("GPM", 328.0839895013123), ("LPM", "100")])
def test_flegere_length(flegere_gdfs, unit, expected_length):
    flegere_gdfs["pipes"].loc[0, "length"] = expected_length
    with pytest.warns(UserWarning, match=r"1 pipes have very different attribute length vs measured length"):
        wn = wq.from_qgis(to_layers(flegere_gdfs), unit)
    assert wn.get_link("1").length == 100


@pytest.mark.parametrize("unit", [("LPS"), ("GPM")])
def test_flegere_calculated_length(flegere_layers, unit):
    wn = wq.from_qgis(flegere_layers, unit)
    assert wn.get_link("1").length == 1724.2674093330734, "calculated length wrong"


def test_flegere_extra_attribute(flegere_gdfs):
    flegere_gdfs["junctions"]["extra_value"] = "extra value"
    flegere_gdfs["pipes"]["extra_number"] = 55
    wn = wq.from_qgis(to_layers(flegere_gdfs), "lps")
    assert wn.get_node("1").extra_value == "extra value"
    assert wn.get_link("1").extra_number == 55
