import warnings

import geopandas as gpd
import pandas as pd
import pytest
import wntr
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant

import wntrqgis as wq
import wntrqgis.elements
import wntrqgis.interface
from wntrqgis.elements import FieldGroup
from wntrqgis.interface import from_qgis


def to_layers(gdfs: dict[str, gpd.GeoDataFrame]) -> dict[str, QgsVectorLayer]:
    return {key: QgsVectorLayer(gdf.to_json(), str(key), "ogr") for key, gdf in gdfs.items()}


def to_gdf(layers: dict[str, QgsVectorLayer]) -> dict[str, gpd.GeoDataFrame]:
    return {key: gpd.GeoDataFrame.from_features(val.getFeatures()) for key, val in layers.items()}


def test_get_field_groups():
    wn = wntr.network.WaterNetworkModel()
    assert wntrqgis.interface._get_field_groups(wn) == FieldGroup(0)

    wn.options.quality.parameter = "CHEMICAL"
    wn.options.report.energy = "YES"
    wn.options.hydraulic.demand_model = "PDD"
    assert (
        wntrqgis.interface._get_field_groups(wn)
        == FieldGroup.PRESSURE_DEPENDENT_DEMAND | FieldGroup.ENERGY | FieldGroup.WATER_QUALITY_ANALYSIS
    )


@pytest.mark.parametrize("example", wntrqgis.examples.values())
def test_examples(example):
    assert example.endswith(".inp")
    wn = wntr.network.WaterNetworkModel(example)
    assert wn
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()
    assert isinstance(results.node["demand"], pd.DataFrame)


@pytest.mark.parametrize("example", wntrqgis.examples.values())
def test_to_qgis(example, qgis_new_project):
    layers = wntrqgis.to_qgis(example)
    assert isinstance(layers, dict)
    assert isinstance(layers["JUNCTIONS"], QgsVectorLayer)
    assert isinstance(layers["PIPES"], QgsVectorLayer)
    assert isinstance(layers["RESERVOIRS"], QgsVectorLayer)
    assert isinstance(layers["TANKS"], QgsVectorLayer)
    assert isinstance(layers["VALVES"], QgsVectorLayer)
    assert isinstance(layers["PUMPS"], QgsVectorLayer)


@pytest.mark.parametrize("example", wntrqgis.examples.values())
def test_to_qgis_results(example, qgis_new_project):
    wn = wntr.network.WaterNetworkModel(example)
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()
    layers = wntrqgis.to_qgis(wn, results)

    assert isinstance(layers, dict)
    assert isinstance(layers["LINKS"], QgsVectorLayer)
    assert isinstance(layers["NODES"], QgsVectorLayer)


@pytest.mark.filterwarnings("ignore: 22 pipes have very different attribute length")
def test_from_qgis(qgis_new_project):
    inpfile = wntrqgis.examples["KY1"]
    layers = wntrqgis.to_qgis(inpfile)

    del layers[wntrqgis.elements.ModelLayer.VALVES]

    new_wn = wntrqgis.from_qgis(layers, "GPM", "H-W", crs="EPSG:3089")

    assert new_wn


def test_empty_wn(qgis_new_project):
    wn = wntr.network.WaterNetworkModel()
    layers = wq.to_qgis(wn)
    assert isinstance(layers, dict)
    assert isinstance(layers["JUNCTIONS"], QgsVectorLayer)


def test_flegere(qgis_new_project, flegere_gdfs):
    flegere_layers = to_layers(flegere_gdfs)
    wn = wq.from_qgis(flegere_layers, "lps", "H-W")
    layers = wq.to_qgis(wn)
    assert isinstance(layers["JUNCTIONS"], QgsVectorLayer)


def test_flegere_broken_layername(qgis_new_project, flegere_layers):
    flegere_layers["wrongname"] = flegere_layers["junctions"]

    with pytest.raises(ValueError, match="'wrongname' is not a valid layer type."):
        wq.from_qgis(flegere_layers, "LPS", "H-W")


@pytest.mark.qgis_show_map(timeout=5, zoom_to_common_extent=True)
def test_flegere_snap(qgis_new_project, flegere_layers):
    QgsProject.instance().addMapLayers(flegere_layers.values())

    wn = wq.from_qgis(flegere_layers, "LPS", "H-W")

    wq.to_qgis(wn)

    wntrqgis.interface.check_network(wn)


def test_flegere_naming(flegere_layers):
    wn = wq.from_qgis(flegere_layers, "lps", "H-W")
    assert wn.node_name_list == ["1", "top_res", "2"]
    assert wn.link_name_list == ["1", "vertex"]


def test_flegere_no_attributes(flegere_gdfs):
    attless_gdfs = {k: gpd.GeoDataFrame(v["geometry"]) for k, v in flegere_gdfs.items()}
    wq.from_qgis(to_layers(attless_gdfs), "lps", "H-W")


@pytest.mark.parametrize(
    ("unit", "expected_demand"),
    {("GPM", 6.30901964e-05), ("SI", 1), ("sI", 1), ("LPS", 0.001), ("lps", 0.001), ("CFS", 0.0283168466)},
)
def test_flegere_conversion(qgis_new_project, flegere_layers, unit, expected_demand):
    wn = wq.from_qgis(flegere_layers, unit, "H-W")
    assert wn.get_node("1").base_demand == expected_demand


def test_flegere_bad_units(qgis_new_project, flegere_layers):
    with pytest.raises(
        ValueError,
        match="Units 'NON-EXISTANT' is not a known set of units. Possible units are: LPS, LPM, MLD, CMH, CFS, GPM, MGD, IMGD, AFD, SI",  # noqa: E501
    ):
        wq.from_qgis(flegere_layers, units="Non-existant", headloss="H-W")


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


def test_to_qgis_valid_crs_string():
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("J1", base_demand=0.01, elevation=10, coordinates=(1, 1))
    wn.add_junction("J2", base_demand=0.02, elevation=20, coordinates=(2, 2))
    wn.add_pipe("P1", "J1", "J2", length=100, diameter=0.3, roughness=100)

    crs = "EPSG:3857"
    layers = wntrqgis.to_qgis(wn, crs=crs)
    assert isinstance(layers, dict)
    assert "JUNCTIONS" in layers
    assert layers["JUNCTIONS"].crs().authid() == crs


def test_to_qgis_valid_crs_object():
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("J1", base_demand=0.01, elevation=10, coordinates=(1, 1))
    wn.add_junction("J2", base_demand=0.02, elevation=20, coordinates=(2, 2))
    wn.add_pipe("P1", "J1", "J2", length=100, diameter=0.3, roughness=100)

    crs = QgsCoordinateReferenceSystem("EPSG:3857")
    layers = wntrqgis.to_qgis(wn, crs=crs)
    assert isinstance(layers, dict)
    assert "JUNCTIONS" in layers
    assert layers["JUNCTIONS"].crs().authid() == crs.authid()


def test_to_qgis_invalid_crs_string():
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("J1", base_demand=0.01, elevation=10, coordinates=(1, 1))
    wn.add_junction("J2", base_demand=0.02, elevation=20, coordinates=(2, 2))
    wn.add_pipe("P1", "J1", "J2", length=100, diameter=0.3, roughness=100)

    crs = "INVALID_CRS"
    with pytest.raises(ValueError, match=f"CRS {crs} is not valid."):
        wntrqgis.to_qgis(wn, crs=crs)


def test_to_qgis_invalid_crs_object():
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("J1", base_demand=0.01, elevation=10, coordinates=(1, 1))
    wn.add_junction("J2", base_demand=0.02, elevation=20, coordinates=(2, 2))
    wn.add_pipe("P1", "J1", "J2", length=100, diameter=0.3, roughness=100)

    crs = QgsCoordinateReferenceSystem("INVALID_CRS")
    with pytest.raises(ValueError, match="is not valid."):
        wntrqgis.to_qgis(wn, crs=crs)


def test_to_qgis_default_crs():
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("J1", base_demand=0.01, elevation=10, coordinates=(1, 1))
    wn.add_junction("J2", base_demand=0.02, elevation=20, coordinates=(2, 2))
    wn.add_pipe("P1", "J1", "J2", length=100, diameter=0.3, roughness=100)

    layers = wntrqgis.to_qgis(wn)
    assert isinstance(layers, dict)
    assert "JUNCTIONS" in layers
    assert layers["JUNCTIONS"].crs().isValid() is False


def test_to_qgis_no_crs():
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("J1", base_demand=0.01, elevation=10, coordinates=(1, 1))
    wn.add_junction("J2", base_demand=0.02, elevation=20, coordinates=(2, 2))
    wn.add_pipe("P1", "J1", "J2", length=100, diameter=0.3, roughness=100)

    layers = wntrqgis.to_qgis(wn, crs=None)
    assert isinstance(layers, dict)
    assert "JUNCTIONS" in layers
    assert layers["JUNCTIONS"].crs().isValid() is False


@pytest.fixture
def qgis_project():
    return QgsProject.instance()


@pytest.fixture
def qgs_layer():
    return QgsVectorLayer("Point", "test_layer", "memory")


@pytest.fixture
def pipe_layer():
    return QgsVectorLayer("LineString", "pipes", "memory")


def setup_layers(qgs_layer, pipe_layer):
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="QgsField constructor is deprecated")
        # Add some nodes to the junctions layer
        provider = qgs_layer.dataProvider()
        provider.addAttributes([QgsField("name", QVariant.String)])
        qgs_layer.updateFields()

        feature1 = QgsFeature()
        feature1.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1, 1)))
        feature1.setAttributes(["J1"])
        provider.addFeature(feature1)

        feature2 = QgsFeature()
        feature2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(2, 2)))
        feature2.setAttributes(["J2"])
        provider.addFeature(feature2)

        qgs_layer.updateExtents()

        # Add some pipes
        pipe_provider = pipe_layer.dataProvider()
        pipe_provider.addAttributes([QgsField("name", QVariant.String)])
        pipe_layer.updateFields()

        pipe_feature = QgsFeature()
        pipe_feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(1, 1), QgsPointXY(2, 2)]))
        pipe_feature.setAttributes(["P1"])
        pipe_provider.addFeature(pipe_feature)

        pipe_layer.updateExtents()


@pytest.mark.parametrize("headloss", ["H-W", "D-W", "C-M"])
def test_from_qgis_headloss(qgis_project, qgs_layer, pipe_layer, headloss):
    setup_layers(qgs_layer, pipe_layer)
    layers = {"JUNCTIONS": qgs_layer, "PIPES": pipe_layer}
    wn = from_qgis(layers, "LPS", headloss=headloss, project=qgis_project)
    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert "J1" in wn.junction_name_list
    assert "J2" in wn.junction_name_list
    assert "P1" in wn.pipe_name_list
    assert wn.options.hydraulic.headloss == headloss


@pytest.mark.skipif(wntr.__version__ == "1.2.0", reason="Problem with headloss conversion in older wntr versions")
@pytest.mark.parametrize(
    ("headloss", "unit", "expected_roughness"),
    [
        ("H-W", "LPS", 100),
        ("D-W", "LPS", 0.1),
        ("C-M", "LPS", 100),
        ("H-W", "SI", 100),
        ("D-W", "SI", 100),
        ("C-M", "SI", 100),
        ("H-W", "GPM", 100),
        ("D-W", "GPM", 0.030480000000000004),
        ("C-M", "GPM", 100),
    ],
)
@pytest.mark.filterwarnings("ignore: QgsField constructor is deprecated")
def test_roughness_conversion(qgis_project, qgs_layer, pipe_layer, headloss, unit, expected_roughness):
    setup_layers(qgs_layer, pipe_layer)
    layers = {"JUNCTIONS": qgs_layer, "PIPES": pipe_layer}
    pipe_layer.dataProvider().addAttributes([QgsField("roughness", QVariant.Double)])
    pipe_layer.updateFields()
    pipe_feature = QgsFeature()
    pipe_feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(1, 1), QgsPointXY(2, 2)]))
    pipe_feature.setAttributes(["P1", 100])  # Roughness in mm
    pipe_layer.dataProvider().addFeature(pipe_feature)
    pipe_layer.updateExtents()

    wn = from_qgis(layers, unit, headloss=headloss, project=qgis_project)
    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert wn.get_link("P1").roughness == expected_roughness


@pytest.mark.filterwarnings("ignore: QgsField constructor is deprecated")
@pytest.mark.skipif(wntr.__version__ == "1.2.0", reason="Problem with headloss conversion in older wntr versions")
@pytest.mark.filterwarnings("ignore:Changing the headloss formula")
@pytest.mark.parametrize(
    ("headloss", "unit", "expected_roughness"),
    [
        ("H-W", "LPS", 100),
        ("D-W", "LPS", 0.1),
        ("C-M", "LPS", 100),
        ("H-W", "SI", 100),
        ("D-W", "SI", 100),
        ("C-M", "SI", 100),
        ("H-W", "GPM", 100),
        ("D-W", "GPM", 0.030480000000000004),
        ("C-M", "GPM", 100),
    ],
)
@pytest.mark.filterwarnings("ignore: QgsField constructor is deprecated")
def test_roughness_conversion_with_wn_options(qgis_project, qgs_layer, pipe_layer, headloss, unit, expected_roughness):
    setup_layers(qgs_layer, pipe_layer)
    layers = {"JUNCTIONS": qgs_layer, "PIPES": pipe_layer}
    pipe_layer.dataProvider().addAttributes([QgsField("roughness", QVariant.Double)])
    pipe_layer.updateFields()
    pipe_feature = QgsFeature()
    pipe_feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(1, 1), QgsPointXY(2, 2)]))
    pipe_feature.setAttributes(["P1", 100])  # Roughness in mm
    pipe_layer.dataProvider().addFeature(pipe_feature)
    pipe_layer.updateExtents()

    wn = wntr.network.WaterNetworkModel()
    wn.options.hydraulic.headloss = headloss

    wn = from_qgis(layers, unit, wn=wn, project=qgis_project)
    assert isinstance(wn, wntr.network.WaterNetworkModel)
    assert wn.get_link("P1").roughness == expected_roughness


def test_from_qgis_invalid_headloss(qgs_layer, pipe_layer):
    setup_layers(qgs_layer, pipe_layer)
    layers = {"JUNCTIONS": qgs_layer, "PIPES": pipe_layer}
    with pytest.raises(ValueError, match="headloss must be set if wn is not set: possible values are: H-W, D-W, C-M"):
        from_qgis(layers, "LPS", headloss=None)


def test_from_qgis_invalid_headloss_with_wn(qgs_layer, pipe_layer):
    setup_layers(qgs_layer, pipe_layer)
    layers = {"JUNCTIONS": qgs_layer, "PIPES": pipe_layer}
    wn = wntr.network.WaterNetworkModel()
    with pytest.raises(
        ValueError,
        match="Cannot set headloss when wn is set. Set the headloss in the wn.options.hydraulic.headloss instead",
    ):
        from_qgis(layers, "LPS", headloss="INVALID", wn=wn)
