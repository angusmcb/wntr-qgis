import importlib.util


def test_install_wntr():
    import wntrqgis.environment_tools

    wntrqgis.environment_tools.install_wntr(False)
    assert importlib.util.find_spec("wntr")
