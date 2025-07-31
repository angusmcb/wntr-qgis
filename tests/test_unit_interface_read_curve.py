import sys

import pytest

import wntrqgis.elements
from wntrqgis.interface import Converter, CurveReadError, _Curves


@pytest.fixture
def wn():
    import wntr

    return wntr.network.WaterNetworkModel()


@pytest.fixture
def converter():
    return Converter(wntrqgis.elements.FlowUnit.LPS, wntrqgis.elements.HeadlossFormula.HAZEN_WILLIAMS)


@pytest.mark.parametrize(
    ("curve_in", "expected_output"),
    [
        ("[(1,2), (3,4)]", [(1.0, 2.0), (3.0, 4.0)]),
        ("[(1.0,2.0), (3,4)]", [(1.0, 2.0), (3.0, 4.0)]),
        ("(1,2)", [(1.0, 2.0)]),
        ("(1,2), (3,4)", [(1.0, 2.0), (3.0, 4.0)]),
        ("[(1,2)]", [(1.0, 2.0)]),
        ("1,2", [(1.0, 2.0)]),
        ("    1   ,2.0", [(1.0, 2.0)]),
        ("[(1,2), (3,4), (5,6), (7,8)]", [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0)]),
        ("('1','2')", [(1.0, 2.0)]),
        ("('1','2'),('3','4')", [(1.0, 2.0), (3.0, 4.0)]),
    ],
)
def test_ok_curve(curve_in, expected_output):
    if curve_in == "    1   ,2.0" and sys.version_info < (3, 10):
        pytest.skip("python 3.9 doesn't work")

    assert _Curves.read_curve(curve_in) == expected_output


@pytest.mark.parametrize(("curve_in", "expected_output"), [("((1,2),(3,4))", [(1.0, 2.0), (3.0, 4.0)])])
def test_curves_unusual_but_ok(curve_in, expected_output):
    assert _Curves.read_curve(curve_in) == expected_output


@pytest.mark.parametrize("curve_in", ["", "     "])
def test_none_curve(curve_in):
    assert _Curves.read_curve(curve_in) is None


@pytest.mark.parametrize(
    "curve_in",
    [
        "[]",
        "[()]",
        "x,y",
        ".3",
        "string",
        "1, 2 , 3, 4",
        "[(1,2), (1,2,3)]",
        "{1,2,3}",
        "[(12)]",
        "(12)",
        "12",
        "(1,2),(3,'y')",
        "(1,2),('x',4)",
        "[(0.0,100),(10.0,1000)],(20,10000.0)",
        "assert False",
        1,
        0,
        1.0,
        0.0,
        True,
        False,
    ],
)
def test_invalid_curve(curve_in):
    with pytest.raises(CurveReadError):
        _Curves.read_curve(curve_in)


def test_curves_add_one(wn, converter):
    curves = _Curves(wn, converter)
    curve_name = curves._add_one("[(1,2), (3,4)]", _Curves.Type.HEAD)
    assert curve_name == "1"


def test_curves_get(wn, converter):
    curves = _Curves(wn, converter)
    curve_name = curves._add_one("[(1,2), (3,4)]", _Curves.Type.HEAD)
    curve = curves.get(curve_name)
    assert curve == "[(1.0, 2.0), (3.0, 4.0)]"


def test_curves_add_invalid(wn, converter):
    curves = _Curves(wn, converter)
    with pytest.raises(wntrqgis.interface.CurveError):
        curves._add_one(None, _Curves.Type.HEAD)
