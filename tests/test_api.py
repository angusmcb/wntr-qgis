import geopandas as gpd
import pytest
import wntr
from qgis.core import QgsProject, QgsVectorLayer

import wntrqgis as wq
import wntrqgis.elements
import wntrqgis.interface


def to_layers(gdfs: dict[str, gpd.GeoDataFrame]) -> dict[str, QgsVectorLayer]:
    return {key: QgsVectorLayer(gdf.to_json(), str(key), "ogr") for key, gdf in gdfs.items()}


def to_gdf(layers: dict[str, QgsVectorLayer]) -> dict[str, gpd.GeoDataFrame]:
    return {key: gpd.GeoDataFrame.from_features(val.getFeatures()) for key, val in layers.items()}


@pytest.mark.filterwarnings("ignore: 22 pipes have very different attribute length")
def test_from_qgis(qgis_new_project):
    inpfile = wntrqgis.examples["KY1"]
    layers = wntrqgis.to_qgis(inpfile)

    del layers[wntrqgis.elements.ModelLayer.VALVES]

    new_wn = wntrqgis.from_qgis(layers, "GPM", "H-W", crs="EPSG:3089")

    assert new_wn


def test_flegere(qgis_new_project, flegere_gdfs):
    flegere_layers = to_layers(flegere_gdfs)
    wn = wq.from_qgis(flegere_layers, "lps", "H-W")
    layers = wq.to_qgis(wn)
    assert isinstance(layers["JUNCTIONS"], QgsVectorLayer)


@pytest.mark.qgis_show_map(timeout=5, zoom_to_common_extent=True)
def test_flegere_snap(qgis_new_project, flegere_layers):
    QgsProject.instance().addMapLayers(flegere_layers.values())

    wn = wq.from_qgis(flegere_layers, "LPS", "H-W")

    wq.to_qgis(wn)

    wntrqgis.interface.check_network(wn)


@pytest.mark.parametrize(
    ("unit", "expected_length"), [("LPS", 100), ("LPS", 100.0), ("GPM", 328.0839895013123), ("LPM", "100")]
)
def test_flegere_length(flegere_gdfs, unit, expected_length):
    flegere_gdfs["pipes"].loc[0, "length"] = expected_length
    with pytest.warns(UserWarning, match=r"1 pipes have very different attribute length vs measured length"):
        wn = wq.from_qgis(to_layers(flegere_gdfs), unit, "H-W")
    assert wn.get_link("1").length == 100


@pytest.mark.parametrize("unit", [("LPS"), ("GPM")])
def test_flegere_calculated_length(flegere_layers, unit):
    wn = wq.from_qgis(flegere_layers, unit, "H-W")
    assert wn.get_link("1").length == 1724.2674093330734, "calculated length wrong"


def test_flegere_extra_attribute(flegere_gdfs):
    flegere_gdfs["junctions"]["extra_value"] = "extra value"
    flegere_gdfs["pipes"]["extra_number"] = 55
    wn = wq.from_qgis(to_layers(flegere_gdfs), "lps", "H-W")
    assert wn.get_node("1").extra_value == "extra value"
    assert wn.get_link("1").extra_number == 55


def test_flegere_load_results(flegere_layers):
    wn = wq.from_qgis(flegere_layers, "lps", "H-W")

    sim = wntr.sim.EpanetSimulator(wn)
    sim_results = sim.run_sim()

    layers = wq.to_qgis(wn, sim_results, units="lps")

    # [print(s) for s in sim_results.node.values()]

    result_gdfs = to_gdf(layers)

    # print(result_gdfs["NODES"])
    # print(result_gdfs["LINKS"].head())

    assert result_gdfs["NODES"].iloc[0]["demand"] == 1.0


def test_flegere_time_results(flegere_layers):
    wn = wq.from_qgis(flegere_layers, "lps", "H-W")
    wn.options.time.duration = 3600
    sim = wntr.sim.EpanetSimulator(wn)
    sim_results = sim.run_sim()

    layers = wq.to_qgis(wn, sim_results, units="lps")

    # [print(s) for s in sim_results.node.values()]

    result_gdfs = to_gdf(layers)

    # print(result_gdfs["NODES"])
    # print(result_gdfs["LINKS"].head())

    assert result_gdfs["NODES"].iloc[0]["demand"] == [1.0, 1.0]
