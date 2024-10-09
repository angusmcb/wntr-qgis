import importlib.util


def test_install_wntr():
    import wntrqgis.environment_tools

    wntrqgis.environment_tools.install_wntr()
    assert importlib.util.find_spec("wntr")
    import wntr

    assert wntr.__version__
