import wntr

import wntrqgis
import wntrqgis.elements
from wntrqgis import interface
from wntrqgis.elements import FieldGroup


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


def test_from_qgis(qgis_new_project):
    inpfile = wntrqgis.Example.KY1
    layers = wntrqgis.to_qgis(inpfile)

    del layers[wntrqgis.elements.ModelLayer.VALVES]

    new_wn = wntrqgis.from_qgis(layers)

    assert new_wn
