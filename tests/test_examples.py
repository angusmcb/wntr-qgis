import pandas as pd
import pytest
import wntr
from qgis.core import QgsVectorLayer

import wntrqgis


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
