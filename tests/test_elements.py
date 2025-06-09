import pytest

from wntrqgis.elements import (
    Field,
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
    [FlowUnit, HeadlossFormula, PumpTypes, InitialStatus, ValveType, TankMixingModel, ModelLayer, ResultLayer, Field],
)
def test_friendly_name(enum):
    for member in enum:
        assert member.friendly_name, f"{member.name} is missing a friendly_name"


def test_field_name_matches_value():
    for field in Field:
        assert field.name.lower() == field.value
