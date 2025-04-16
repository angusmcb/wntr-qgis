#!/usr/bin/env python
import glob
from pathlib import Path

import qgis_plugin_tools.infrastructure.plugin_maker as pm
import qgis_plugin_tools.tools.resources as r
from qgis_plugin_tools.infrastructure.plugin_maker import PluginMaker

"""
#################################################
# Edit the following to match the plugin
#################################################
"""

locales = ["en", "fr", "es", "de", "pt", "it", "ar", "nl"]
py_files = [fil for fil in glob.glob("wntrqgis/**/*.py", recursive=True) if "packages" not in fil]
ui_files = list(glob.glob("**/*.ui", recursive=True))
resources = list(glob.glob("**/*.qrc", recursive=True))
extra_dirs = ["resources"]
compiled_resources = ["resources.py"]


# print(r._IS_SUBMODULE_USAGE)

# # pm.plugin_path = lambda:
# print(r.plugin_path())
# print("here")
# print(pm.PLUGIN_PACKAGE_NAME)
# print(pm.ROOT_DIR)

r.plugin_path = lambda: str((Path(__file__).parent / "wntrqgis").resolve())

pm.PLUGIN_PACKAGE_NAME = "wntrqgis"
pm.ROOT_DIR = str((Path(__file__).parent / "wntrqgis").resolve())
PluginMaker(
    py_files=py_files,
    ui_files=ui_files,
    resources=resources,
    extra_dirs=extra_dirs,
    compiled_resources=compiled_resources,
    locales=locales,
    submodules=[],
)
