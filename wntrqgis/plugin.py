from __future__ import annotations

import os
import subprocess
import sys

this_dir = os.path.dirname(os.path.realpath(__file__))
path = os.path.join(this_dir, "packages")
sys.path.append(path)


from typing import Callable

from qgis.core import Qgis, QgsApplication
from qgis.PyQt.QtCore import QCoreApplication, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QWidget
from qgis.utils import iface

from wntrqgis.qgis_plugin_tools.tools.custom_logging import setup_logger, teardown_logger
from wntrqgis.qgis_plugin_tools.tools.i18n import setup_translation
from wntrqgis.qgis_plugin_tools.tools.resources import plugin_name
from wntrqgis.wntrqgis_processing.provider import Provider


class Plugin:
    """QGIS Plugin Implementation."""

    name = plugin_name()
    missing_deps = []

    def __init__(self) -> None:
        setup_logger(Plugin.name)

        # initialize locale
        locale, file_path = setup_translation()
        if file_path:
            self.translator = QTranslator()
            self.translator.load(file_path)
            # noinspection PyCallByClass
            QCoreApplication.installTranslator(self.translator)
        else:
            pass

        self.check_deps()

        self.actions: list[QAction] = []
        self.menu = Plugin.name

    def check_deps(self):
        missing_deps = []
        try:
            import pandas
        except ImportError:
            missing_deps.append("pandas")
        try:
            import numpy
        except ImportError:
            missing_deps.append("numpy")
        try:
            import scipy
        except ImportError:
            missing_deps.append("scipy")
        try:
            import networkx
        except ImportError:
            missing_deps.append("networkx")
        try:
            import matplotlib
        except ImportError:
            missing_deps.append("matplotlib")

        if len(missing_deps) == 0:
            try:
                import wntr
            except ImportError:
                this_dir = os.path.dirname(os.path.realpath(__file__))
                wheels = os.path.join(this_dir, "wheels/")
                scripts = os.path.join(this_dir, "packages/")

                subprocess.run(
                    [
                        "python",
                        "-m",
                        "pip",
                        "install",
                        "--no-index",
                        "--upgrade",
                        "--target=" + scripts,
                        "--no-deps",
                        "--find-links=" + wheels,
                        "wntr",
                    ],
                    check=False,
                )
                try:
                    import wntr
                except ImportError:
                    missing_deps.append("wntr")
        self.missing_deps = missing_deps

    def add_action(
        self,
        icon_path: str,
        text: str,
        callback: Callable,
        *,
        enabled_flag: bool = True,
        add_to_menu: bool = True,
        add_to_toolbar: bool = True,
        status_tip: str | None = None,
        whats_this: str | None = None,
        parent: QWidget | None = None,
    ) -> QAction:
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.

        :param text: Text that should be shown in menu items for this action.

        :param callback: Function to be called when the action is triggered.

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.

        :param parent: Parent widget for the new action. Defaults None.

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            iface.addToolBarIcon(action)

        if add_to_menu:
            iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initProcessing(self):  # noqa N802
        self.provider = Provider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self) -> None:  # noqa N802
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        if len(self.missing_deps):
            iface.messageBar().pushMessage(
                "Error", "Missing dependencies " + ", ".join(self.missing_deps), level=Qgis.Warning
            )

        self.add_action(
            "",
            text=Plugin.name,
            callback=self.run,
            parent=iface.mainWindow(),
            add_to_toolbar=False,
        )
        self.initProcessing()

    def onClosePlugin(self) -> None:  # noqa N802
        """Cleanup necessary items here when plugin dockwidget is closed"""

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            iface.removePluginMenu(Plugin.name, action)
            iface.removeToolBarIcon(action)
        teardown_logger(Plugin.name)
        QgsApplication.processingRegistry().removeProvider(self.provider)

    def run(self) -> None:
        """Run method that performs all the real work"""
        print("Hello QGIS plugin")  # noqa: T201
