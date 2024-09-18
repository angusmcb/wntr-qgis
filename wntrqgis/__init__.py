import os
from typing import TYPE_CHECKING

from wntrqgis.qgis_plugin_tools.infrastructure.debugging import (
    setup_debugpy,  # noqa F401
    setup_ptvsd,  # noqa F401
    setup_pydevd,  # noqa F401
)
from wntrqgis.scratch import importinp
from wntrqgis.utils import to_wn_gis

if TYPE_CHECKING:
    from qgis.gui import QgisInterface

debugger = os.environ.get("QGIS_PLUGIN_USE_DEBUGGER", "").lower()
if debugger in {"debugpy", "ptvsd", "pydevd"}:
    locals()["setup_" + debugger]()


def classFactory(iface: "QgisInterface"):  # noqa N802
    from wntrqgis.plugin import Plugin

    return Plugin()
