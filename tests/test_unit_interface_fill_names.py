# ruff: noqa: PD901

import functools

import numpy as np
import pandas as pd
import pytest

from wntrqgis import interface


@pytest.fixture(scope="module")
def fill_names():
    fill_names = functools.partial(interface._FromGis._fill_names, interface._FromGis)
    return interface.needs_wntr_pandas(fill_names)


def test_fill_names_all_pdna(fill_names):
    df = pd.DataFrame({"name": [pd.NA, pd.NA, pd.NA]})

    fill_names(df)

    assert df["name"].to_list() == ["1", "2", "3"]


def test_fill_names_all_nan(fill_names):
    df = pd.DataFrame({"name": [np.nan, np.nan, np.nan]})

    fill_names(df)

    assert df["name"].to_list() == ["1", "2", "3"]


def test_fill_names_all_none(fill_names):
    df = pd.DataFrame({"name": [None, None, None]})

    fill_names(df)

    assert df["name"].to_list() == ["1", "2", "3"]


def test_fill_names_all_empty_string(fill_names):
    df = pd.DataFrame({"name": ["", "", ""]})

    fill_names(df)

    assert df["name"].to_list() == ["1", "2", "3"]


def test_fill_names_all_string_whitespace(fill_names):
    df = pd.DataFrame({"name": ["  ", "  ", "  "]})

    fill_names(df)

    assert df["name"].to_list() == ["1", "2", "3"]


def test_fill_names_some_missing(fill_names):
    df = pd.DataFrame({"name": ["a", pd.NA, "b", "", "   "]})

    fill_names(df)

    assert df["name"].to_list() == ["a", "1", "b", "2", "3"]


def test_fill_names_existing_names(fill_names):
    df = pd.DataFrame({"name": ["1", "2", pd.NA, "3", ""]})

    fill_names(df)

    assert df["name"].to_list() == ["1", "2", "4", "3", "5"]


def test_fill_names_no_name_column(fill_names):
    df = pd.DataFrame({"other": [1, 2, 3]})

    fill_names(df)

    assert "name" in df.columns
    assert df["name"].to_list() == ["1", "2", "3"]


def test_fill_names_object_str_names(fill_names):
    df = pd.DataFrame({"name": ["1", "2", "3", "4"]}, dtype="object")

    fill_names(df)

    assert df["name"].to_list() == ["1", "2", "3", "4"]


def test_fill_names_new_str_names(fill_names):
    df = pd.DataFrame({"name": ["1", "2", "3", "4"]}, dtype="string")

    fill_names(df)

    assert df["name"].to_list() == ["1", "2", "3", "4"]


def test_fill_names_float_names(fill_names):
    df = pd.DataFrame({"name": [1.0, 2.0, 3.0, 4.0]}, dtype="float64")

    fill_names(df)

    assert df["name"].to_list() == ["1.0", "2.0", "3.0", "4.0"]


def test_fill_names_int_names(fill_names):
    df = pd.DataFrame({"name": [1, 2, 3, 4]}, dtype="int8")

    fill_names(df)

    assert df["name"].to_list() == ["1", "2", "3", "4"]


def test_fill_names_bool_names(fill_names):
    df = pd.DataFrame({"name": [True, False]}, dtype="bool")

    fill_names(df)

    assert df["name"].to_list() == ["True", "False"]


def test_fill_names_strip_spaces(fill_names):
    df = pd.DataFrame({"name": ["a", " ", "b", ""]})
    fill_names(df)
    assert df["name"].notna().all()
    assert df["name"].is_unique
    assert len(set(df["name"])) == 4
    assert "a" in df["name"].to_numpy()
    assert "b" in df["name"].to_numpy()


def test_fill_names_non_string_name_column(fill_names):
    df = pd.DataFrame({"name": [1, 2, pd.NA, 4]})

    fill_names(df)

    assert df["name"].to_list() == ["1", "2", "3", "4"]


def test_fill_names_all_empty_strings(fill_names):
    df = pd.DataFrame({"name": ["", "   ", ""]})

    fill_names(df)

    assert df["name"].to_list() == ["1", "2", "3"]


def test_fill_names_all_duplicates(fill_names):
    df = pd.DataFrame({"name": ["dup", "dup", "dup"]})
    fill_names(df)

    assert df["name"].notna().all()
    assert "dup" in df["name"].to_numpy()
    assert len(df["name"]) == 3


def test_fill_names_mixed_types(fill_names):
    df = pd.DataFrame({"name": ["a", 1, None, 2.0, ""]})

    fill_names(df)

    assert df["name"].to_list() == ["a", "1", "2", "2.0", "3"]


def test_fill_names_large_number(fill_names):
    n = 100_000
    df = pd.DataFrame({"name": [pd.NA] * n})

    fill_names(df)

    assert not df["name"].hasnans
    assert df["name"].is_unique


def test_fill_names_with_nan(fill_names):
    df = pd.DataFrame({"name": ["a", np.nan, "b", None, ""]})
    fill_names(df)

    assert df["name"].to_list() == ["a", "1", "b", "2", "3"]
