import platform
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


major, minor, _ = platform.python_version_tuple()
packages_path = Path(__file__).parent / "packages" / (major + minor)
packages_path.mkdir(parents=True, exist_ok=True)
sys.path.append(str(packages_path.resolve()))
