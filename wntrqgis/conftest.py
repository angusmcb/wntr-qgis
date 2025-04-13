# content of conftest.py
import pytest


@pytest.fixture(scope="session")
def check_wntr():
    from wntrqgis.dependency_management import WqDependencyManagement

    WqDependencyManagement.ensure_wntr()


@pytest.fixture(autouse=True)
def add_wntr(check_wntr, doctest_namespace):  # noqa: ARG001
    import wntr

    doctest_namespace["wntr"] = wntr
