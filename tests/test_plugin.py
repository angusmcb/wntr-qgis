def test_load_plugin(qgis_app, qgis_iface):
    import qgis.utils

    assert qgis.utils.loadPlugin("wntrqgis")


def test_class_factory(qgis_app, qgis_iface):
    from qgis.utils import iface

    import wntrqgis

    plugin_class = wntrqgis.classFactory(iface)

    assert plugin_class
    plugin_class.initGui()
    plugin_class.initProcessing()


def test_actions(qgis_app, qgis_iface, qgis_processing):
    # from qgis.PyQt.QtWidgets import QAction

    import wntrqgis.plugin

    plugin_class = wntrqgis.plugin.Plugin()
    plugin_class.initGui()
    plugin_class.initProcessing()

    # for action in plugin_class.actions:
    #     action.activate(QAction.Trigger)

    # plugin_class.load_example()
