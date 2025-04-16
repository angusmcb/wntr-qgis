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


@pytest.mark.parametrize(
    "enum",
    [FlowUnit, HeadlossFormula, PumpTypes, InitialStatus, ValveType, ModelLayer, ResultLayer, ModelField, ResultField],
)
def test_friendly_name(enum):
    for member in enum:
        assert member.friendly_name, f"{member.name} is missing a friendly_name"


@pytest.mark.parametrize("enum", [ModelField, ResultField])
def test_field_name_matches_value(enum):
    for field in enum:
        assert field.name.lower() == field.value.lower()
