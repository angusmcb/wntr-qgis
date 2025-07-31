import numpy as np
import pandas as pd
import pytest

import wntrqgis.elements
from wntrqgis.elements import Field, FlowUnit, HeadlossFormula, Parameter
from wntrqgis.units import Converter


@pytest.fixture
def converter():
    return Converter(FlowUnit.LPS, HeadlossFormula.HAZEN_WILLIAMS)


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


def test_to_si_float(converter):
    value = 10.0
    # FlowUnit.LPS: factor = 0.001
    expected = 0.01
    result = converter.to_si(value, Field.FLOWRATE)
    assert result == expected


def test_from_si_float(converter):
    value = 10.0
    # FlowUnit.LPS: factor = 0.001
    expected = 10000.0
    result = converter.from_si(value, Field.FLOWRATE)
    assert result == expected


def test_to_si_numpy_array(converter):
    value = np.array([1.0, 2.0, 3.0])
    expected = np.array([0.001, 0.002, 0.003])
    result = converter.to_si(value, Field.FLOWRATE)
    np.testing.assert_array_almost_equal(result, expected)


def test_from_si_numpy_array(converter):
    value = np.array([1.0, 2.0, 3.0])
    expected = np.array([1000.0, 2000.0, 3000.0])
    result = converter.from_si(value, Field.FLOWRATE)
    np.testing.assert_array_almost_equal(result, expected)


def test_to_si_pandas_series(converter):
    value = pd.Series([1.0, 2.0, 3.0])
    expected = pd.Series([0.001, 0.002, 0.003])
    result = converter.to_si(value, Field.FLOWRATE)
    pd.testing.assert_series_equal(result, expected)


def test_from_si_pandas_series(converter):
    value = pd.Series([1.0, 2.0, 3.0])
    expected = pd.Series([1000.0, 2000.0, 3000.0])
    result = converter.from_si(value, Field.FLOWRATE)
    pd.testing.assert_series_equal(result, expected)


def test_to_si_pandas_dataframe(converter):
    value = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    expected = pd.DataFrame({"a": [0.001, 0.002], "b": [0.003, 0.004]})
    result = converter.to_si(value, Field.FLOWRATE)
    pd.testing.assert_frame_equal(result, expected)


def test_from_si_pandas_dataframe(converter):
    value = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    expected = pd.DataFrame({"a": [1000.0, 2000.0], "b": [3000.0, 4000.0]})
    result = converter.from_si(value, Field.FLOWRATE)
    pd.testing.assert_frame_equal(result, expected)
