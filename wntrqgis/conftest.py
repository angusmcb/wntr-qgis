# content of conftest.py
import pytest
import wntr


@pytest.fixture(autouse=True)
def add_wntr(doctest_namespace):
    doctest_namespace["wntr"] = wntr
