__all__ = ["examples", "from_qgis", "to_qgis"]

import codecs
import configparser
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import wntrqgis.dependency_management
from wntrqgis.interface import from_qgis, to_qgis

_packages_path = wntrqgis.dependency_management.WntrInstaller.package_directory()
if _packages_path not in sys.path:
    sys.path.append(_packages_path)


# from wntrqgis.qgis_plugin_tools.infrastructure.debugging import (
#     setup_debugpy,
#     setup_ptvsd,
#     setup_pydevd,
# )

if TYPE_CHECKING:  # pragma: no cover
    from qgis.gui import QgisInterface

# debugger = os.environ.get("QGIS_PLUGIN_USE_DEBUGGER", "").lower()
# if debugger in {"debugpy", "ptvsd", "pydevd"}:
#     locals()["setup_" + debugger]()


_cp = configparser.ConfigParser()
with codecs.open(str(Path(__file__).parent / "metadata.txt"), "r", "utf8") as f:
    _cp.read_file(f)
__version__ = _cp.get("general", "version")


def _inp_path(example_name: str) -> str:
    return str(Path(__file__).resolve().parent / "resources" / "examples" / (example_name + ".inp"))


examples = {
    "KY1": _inp_path("ky1"),
    "KY10": _inp_path("ky10"),
    "VALVES": _inp_path("valves"),
}


def classFactory(iface: "QgisInterface"):  # noqa N802
    from wntrqgis.plugin import Plugin

    return Plugin()
