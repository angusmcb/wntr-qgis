import pytest


@pytest.fixture(autouse=True, scope="session")
def check_wntr():
    from wntrqgis.dependency_management import WntrInstaller

    try:
        import wntr  # type: ignore # noqa F401
    except ImportError:
        WntrInstaller.install_wntr()


@pytest.fixture(autouse=True)
def add_wntr(check_wntr, doctest_namespace):  # noqa: ARG001
    import wntr  # type: ignore

    doctest_namespace["wntr"] = wntr
