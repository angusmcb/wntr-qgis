import pytest

from wntrqgis.elements import (
    DemandType,
    Field,
    FieldType,
    FlowUnit,
    HeadlossFormula,
    InitialStatus,
    ModelLayer,
    PumpTypes,
    ResultLayer,
    TankMixingModel,
    ValveType,
)


@pytest.mark.parametrize(
    "enum",
    [
        FlowUnit,
        HeadlossFormula,
        PumpTypes,
        InitialStatus,
        ValveType,
        TankMixingModel,
        ModelLayer,
        ResultLayer,
        Field,
        DemandType,
    ],
)
def test_friendly_name(enum):
    for member in enum:
        assert member.friendly_name, f"{member.name} is missing a friendly_name"


@pytest.mark.parametrize(
    "enum",
    [
        FlowUnit,
        HeadlossFormula,
        PumpTypes,
        InitialStatus,
        ValveType,
        TankMixingModel,
        ModelLayer,
        ResultLayer,
        Field,
        DemandType,
    ],
)
def test_translated_name(enum, monkeypatch: pytest.MonkeyPatch):
    translated_string = "xxx"
    monkeypatch.setattr("wntrqgis.elements.tr", lambda *args: translated_string)
    for member in enum:
        assert member.friendly_name == translated_string, f"{member.name}.friendly_name is not translated"


def test_field_name_matches_value():
    for field in Field:
        assert field.name.lower() == field.value


@pytest.mark.parametrize("field", list(Field))
def test_field_types(field: Field):
    assert isinstance(field.type, FieldType), f"{field.name}.value is not a FieldType"
