import sys
from pathlib import Path
from typing import TYPE_CHECKING

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


packages_path = Path(__file__).parent / "packages"
packages_path.mkdir(exist_ok=True)
sys.path.append(str(packages_path.resolve()))
