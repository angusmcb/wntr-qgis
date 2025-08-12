import functools

import numpy as np
import pandas as pd
import pytest

from gusnet import interface


@pytest.fixture(scope="module")
def fill_names():
    fill_names = functools.partial(interface._FromGis._fill_names, interface._FromGis)
    return interface.needs_wntr_pandas(fill_names)


def test_fill_names_all_pdna(fill_names):
    df = pd.DataFrame({"name": [pd.NA, pd.NA, pd.NA]})

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "3"]


def test_fill_names_all_nan(fill_names):
    df = pd.DataFrame({"name": [np.nan, np.nan, np.nan]})

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "3"]


def test_fill_names_all_none(fill_names):
    df = pd.DataFrame({"name": [None, None, None]})

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "3"]


def test_fill_names_all_empty_string(fill_names):
    df = pd.DataFrame({"name": ["", "", ""]})

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "3"]


def test_fill_names_all_string_whitespace(fill_names):
    df = pd.DataFrame({"name": ["  ", "  ", "  "]})

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "3"]


def test_fill_names_some_missing(fill_names):
    df = pd.DataFrame({"name": ["a", pd.NA, "b", "", "   "]})

    names = fill_names(df)

    assert names.to_list() == ["a", "1", "b", "2", "3"]


def test_fill_names_existing_names(fill_names):
    df = pd.DataFrame({"name": ["1", "2", pd.NA, "3", ""]})

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "4", "3", "5"]


def test_fill_names_no_name_column(fill_names):
    df = pd.DataFrame({"other": [1, 2, 6]})

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "3"]


def test_fill_names_object_str_names(fill_names):
    df = pd.DataFrame({"name": ["1", "2", "3", "4"]}, dtype="object")

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "3", "4"]


def test_fill_names_new_str_names(fill_names):
    df = pd.DataFrame({"name": ["1", "2", "3", "4"]}, dtype="string")

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "3", "4"]


def test_fill_names_float_names(fill_names):
    df = pd.DataFrame({"name": [1.0, 2.0, 3.0, 4.0]}, dtype="float64")

    names = fill_names(df)

    assert names.to_list() == ["1.0", "2.0", "3.0", "4.0"]


def test_fill_names_int_names(fill_names):
    df = pd.DataFrame({"name": [1, 2, 3, 4]}, dtype="int8")

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "3", "4"]


def test_fill_names_bool_names(fill_names):
    df = pd.DataFrame({"name": [True, False]}, dtype="bool")

    names = fill_names(df)

    assert names.to_list() == ["True", "False"]


def test_fill_names_strip_spaces(fill_names):
    df = pd.DataFrame({"name": ["a", " ", "b", ""]})

    names = fill_names(df)

    assert names.notna().all()
    assert names.is_unique
    assert len(set(names)) == 4
    assert "a" in names.to_numpy()
    assert "b" in names.to_numpy()


def test_fill_names_non_string_name_column(fill_names):
    df = pd.DataFrame({"name": [1, 2, pd.NA, 4]})

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "3", "4"]


def test_fill_names_all_empty_strings(fill_names):
    df = pd.DataFrame({"name": ["", "   ", ""]})

    names = fill_names(df)

    assert names.to_list() == ["1", "2", "3"]


def test_fill_names_all_duplicates(fill_names):
    df = pd.DataFrame({"name": ["dup", "dup", "dup"]})

    names = fill_names(df)

    assert names.notna().all()
    assert "dup" in names.to_numpy()
    assert len(names) == 3


def test_fill_names_mixed_types(fill_names):
    df = pd.DataFrame({"name": ["a", 1, None, 2.0, ""]})

    names = fill_names(df)

    assert names.to_list() == ["a", "1", "2", "2.0", "3"]


def test_fill_names_large_number(fill_names):
    n = 100_000
    df = pd.DataFrame({"name": [pd.NA] * n})

    names = fill_names(df)

    assert not names.hasnans
    assert names.is_unique


def test_fill_names_with_nan(fill_names):
    df = pd.DataFrame({"name": ["a", np.nan, "b", None, ""]})

    names = fill_names(df)

    assert names.to_list() == ["a", "1", "b", "2", "3"]
