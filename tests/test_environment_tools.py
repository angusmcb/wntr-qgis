import importlib.util


def test_install_wntr():
    import wntrqgis.environment_tools

    wntrqgis.environment_tools.install_wntr(True)
    assert importlib.util.find_spec("wntrqgis.packages.wntr")
