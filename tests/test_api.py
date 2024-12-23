import wntr

import wntrqgis
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
