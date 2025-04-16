import pytest

from wntrqgis.elements import (
    FlowUnit,
    HeadlossFormula,
    InitialStatus,
    ModelField,
    ModelLayer,
    PumpTypes,
    ResultField,
    ResultLayer,
    ValveType,
)


@pytest.mark.parametrize("unit", list(FlowUnit))
def test_flow_unit_friendly_name(unit):
    assert unit.friendly_name, f"{unit.name} is missing a friendly_name"


@pytest.mark.parametrize("formula", list(HeadlossFormula))
def test_headloss_formula_friendly_name(formula):
    assert formula.friendly_name, f"{formula.name} is missing a friendly_name"


@pytest.mark.parametrize("pump_type", list(PumpTypes))
def test_pump_types_friendly_name(pump_type):
    assert pump_type.friendly_name, f"{pump_type.name} is missing a friendly_name"


@pytest.mark.parametrize("status", list(InitialStatus))
def test_initial_status_friendly_name(status):
    assert status.friendly_name, f"{status.name} is missing a friendly_name"


@pytest.mark.parametrize("valve_type", list(ValveType))
def test_valve_type_friendly_name(valve_type):
    assert valve_type.friendly_name, f"{valve_type.name} is missing a friendly_name"


@pytest.mark.parametrize("layer", list(ModelLayer))
def test_model_layer_friendly_name(layer):
    assert layer.friendly_name, f"{layer.name} is missing a friendly_name"


@pytest.mark.parametrize("layer", list(ResultLayer))
def test_result_layer_friendly_name(layer):
    assert layer.friendly_name, f"{layer.name} is missing a friendly_name"


@pytest.mark.parametrize("field", list(ModelField))
def test_model_field_name_matches_value(field):
    assert field.name.lower() == field.value.lower(), f"{field.name} != {field.value}"


@pytest.mark.parametrize("field", list(ModelField))
def test_model_field_friendly_name(field):
    assert field.friendly_name, f"{field.name} is missing a friendly_name"


@pytest.mark.parametrize("field", list(ResultField))
def test_result_field_name_matches_value(field):
    assert field.name.lower() == field.value.lower(), f"{field.name} != {field.value}"


@pytest.mark.parametrize("field", list(ResultField))
def test_result_field_friendly_name(field):
    assert field.friendly_name, f"{field.name} is missing a friendly_name"
