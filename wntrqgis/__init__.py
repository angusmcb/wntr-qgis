import sys
from typing import TYPE_CHECKING

import wntrqgis.dependency_management

# from wntrqgis.qgis_plugin_tools.infrastructure.debugging import (
#     setup_debugpy,
#     setup_ptvsd,
#     setup_pydevd,
# )

if TYPE_CHECKING:
    from qgis.gui import QgisInterface

# debugger = os.environ.get("QGIS_PLUGIN_USE_DEBUGGER", "").lower()
# if debugger in {"debugpy", "ptvsd", "pydevd"}:
#     locals()["setup_" + debugger]()


def classFactory(iface: "QgisInterface"):  # noqa N802
    from wntrqgis.plugin import Plugin

    return Plugin()


packages_path = wntrqgis.dependency_management.WqDependencyManagement.package_directory()
if packages_path not in sys.path:
    sys.path.append(packages_path)
