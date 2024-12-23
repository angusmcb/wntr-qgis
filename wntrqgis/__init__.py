__all__ = ["to_qgis", "from_qgis", "Example"]

import codecs
import configparser
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import wntrqgis.dependency_management
from wntrqgis.interface import from_qgis, to_qgis
from wntrqgis.resource_manager import Example

packages_path = wntrqgis.dependency_management.WqDependencyManagement.package_directory()
if packages_path not in sys.path:
    sys.path.append(packages_path)


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


metadata_file = Path(__file__).parent / "metadata.txt"
cp = configparser.ConfigParser()
with codecs.open(str(metadata_file), "r", "utf8") as f:
    cp.read_file(f)
__version__ = cp.get("general", "version")


def classFactory(iface: "QgisInterface"):  # noqa N802
    from wntrqgis.plugin import Plugin

    return Plugin()
