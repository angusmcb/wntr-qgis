__all__ = ["to_qgis", "from_qgis", "examples"]

import codecs
import configparser
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import wntrqgis.dependency_management
from wntrqgis.interface import from_qgis, to_qgis
from wntrqgis.resource_manager import Example, examples

_packages_path = wntrqgis.dependency_management.WqDependencyManagement.package_directory()
if _packages_path not in sys.path:
    sys.path.append(_packages_path)


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


_cp = configparser.ConfigParser()
with codecs.open(str(Path(__file__).parent / "metadata.txt"), "r", "utf8") as f:
    _cp.read_file(f)
__version__ = _cp.get("general", "version")


def classFactory(iface: "QgisInterface"):  # noqa N802
    from wntrqgis.plugin import Plugin

    return Plugin()
