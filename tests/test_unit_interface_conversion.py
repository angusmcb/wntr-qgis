import pytest

import wntrqgis.elements
from wntrqgis.elements import Field
from wntrqgis.interface import (
    UnitError,
    _Converter,
)


def test_converter_init():
    import wntr

    converter = _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)
    assert converter._flow_units == wntr.epanet.FlowUnits.LPS
    assert not converter._darcy_weisbach


def test_converter_to_si():
    converter = _Converter("CFS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)
    value = converter.to_si(1.0, wntrqgis.elements.Field.ELEVATION)
    assert value == 0.3048


def test_converter_from_si():
    converter = _Converter("CFS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)
    value = converter.from_si(0.3048, wntrqgis.elements.Field.ELEVATION)
    assert value == 1.0


def test_converter_to_si_darcy_weisbach():
    converter = _Converter("LPS", wntrqgis.elements.HeadlossFormula.DARCY_WEISBACH)
    value = converter.to_si(1, wntrqgis.elements.Field.ROUGHNESS)
    assert value == 0.001


def test_converter_to_si_hazen_williams():
    converter = _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)
    value = converter.to_si(1, wntrqgis.elements.Field.ROUGHNESS)
    assert value == 1


def test_converter_invalid_units():
    with pytest.raises(UnitError):
        _Converter("INVALID_UNIT", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)


@pytest.mark.parametrize("field", list(Field))
def test_get_conversion_param(field):
    import wntr

    converter = _Converter("LPS", wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)

    conversion_parameter = converter._get_wntr_conversion_param(field)

    assert isinstance(conversion_parameter, (type(None), wntr.epanet.HydParam, wntr.epanet.QualParam))
