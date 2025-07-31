import pytest

import wntrqgis.elements
from wntrqgis.elements import Field, FlowUnit, HeadlossFormula, Parameter
from wntrqgis.units import Converter


def test_converter_to_si():
    converter = Converter(FlowUnit.CFS, HeadlossFormula.HAZEN_WILLIAMS)
    value = converter.to_si(1.0, Field.ELEVATION)
    assert value == 0.3048


def test_converter_from_si():
    converter = Converter(FlowUnit.CFS, HeadlossFormula.HAZEN_WILLIAMS)
    value = converter.from_si(0.3048, wntrqgis.elements.Field.ELEVATION)
    assert value == 1.0


def test_converter_to_si_darcy_weisbach():
    converter = Converter(FlowUnit.LPS, HeadlossFormula.DARCY_WEISBACH)
    value = converter.to_si(1, wntrqgis.elements.Field.ROUGHNESS)
    assert value == 0.001


def test_converter_to_si_hazen_williams():
    converter = Converter(FlowUnit.CFS, HeadlossFormula.HAZEN_WILLIAMS)
    value = converter.to_si(1, wntrqgis.elements.Field.ROUGHNESS)
    assert value == 1


@pytest.mark.parametrize("field", list(Field))
def test_get_conversion_param(field):
    converter = Converter(FlowUnit.LPS, wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)

    conversion_parameter = converter._get_conversion_param(field)

    assert isinstance(conversion_parameter, (type(None), Parameter))


@pytest.mark.parametrize("param", list(Parameter))
@pytest.mark.parametrize("flow_unit", list(FlowUnit))
@pytest.mark.parametrize("headloss_formula", list(HeadlossFormula))
def test_factor_in_all_combinations(param, flow_unit, headloss_formula):
    converter = Converter(flow_unit, headloss_formula)

    factor = converter._factor(param)

    assert isinstance(factor, float)
