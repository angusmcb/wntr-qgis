# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
from enum import Enum
from pathlib import Path

import pandas as pd

project = "Water Network Tools for Resiliance - QGIS Integration"
project_copyright = "2024, Angus McBride"
author = "Angus McBride"
release = "0.1.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "enum_tools.autoenum",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]
html_logo = "../wntrqgis/resources/icons/logo.svg"
html_favicon = html_logo

html_theme_options = {
    "logo": {"text": "WNTR-QGIS"},
    "icon_links": [
        {
            # Label for this link
            "name": "GitHub",
            # URL where the link will redirect
            "url": "https://github.com/angusmcb/wntr-qgis",  # required
            # Icon class (if "type": "fontawesome"), or path to local image (if "type": "local")
            "icon": "fa-brands fa-github",
            # The type of image to be used (see below for details)
            "type": "fontawesome",
        },
        {
            # Label for this link
            "name": "QGIS",
            # URL where the link will redirect
            "url": "https://qgis.org/",  # required
            # Icon class (if "type": "fontawesome"), or path to local image (if "type": "local")
            "icon": "_static/qgis-32x32.png",
            # The type of image to be used (see below for details)
            "type": "local",
        },
        {
            # Label for this link
            "name": "WNTR",
            # URL where the link will redirect
            "url": "https://usepa.github.io/WNTR/",  # required
            # Icon class (if "type": "fontawesome"), or path to local image (if "type": "local")
            "icon": "_static/water_circle.png",
            # The type of image to be used (see below for details)
            "type": "local",
        },
    ],
}


intersphinx_mapping = {
    "qgis": ("https://qgis.org/pyqgis/master/", None),
    "wntr": ("https://usepa.github.io/WNTR/", None),
    "python": ("https://docs.python.org/3", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "qgisdocs": ("https://docs.qgis.org/latest/en/", None),
    "epanet": ("https://epanet22.readthedocs.io/en/latest/", None),
}
myst_url_schemes = [
    "http",
    "https",
]


numfig = True
numfig_format = {"figure": "Figure %s", "table": "Table %s", "code-block": "Listing %s"}


sys.path.insert(0, os.path.abspath(".."))

autodoc_type_aliases = {"Iterable": "Iterable", "ArrayLike": "ArrayLike"}
# add_module_names = False
autodoc_member_order = "bysource"


def generate_attributes_table(_):
    from wntrqgis.elements import ModelLayer

    output_dir = Path(__file__).parent / "user_guide" / "autogen-includes"
    output_dir.mkdir(parents=True, exist_ok=True)
    for layer in ModelLayer:
        table = pd.DataFrame(
            [
                (field.value, field_type_str(field, layer), field_value(field, layer), field_analysis_type(field))
                for field in layer.wq_fields()
            ],
            columns=["Attribute", "QGIS Field Type", "Value(s)", "Used for"],
        )
        table.to_csv(output_dir / (layer.name.lower() + ".csv"), index=False)


def field_type_str(field, layer):
    from wntrqgis.elements import CurveType, InitialStatus, ModelLayer, PatternType

    python_type = field.python_type
    # if issubclass(python_type, Enum):
    #     if python_type is InitialStatus and layer is ModelLayer.PIPES:
    #         enum_list = [InitialStatus.Open, InitialStatus.Closed]
    #     else:
    #         enum_list = python_type.__members__
    #     return ", ".join(enum_list)
    if issubclass(python_type, PatternType):
        return "Text (string) *or* Decimal list"
    # if issubclass(python_type, CurveType):
    #     return "Text (string)"
    if issubclass(python_type, str):
        return "Text (string)"
    if python_type is float:
        return "Decimal (double)"
    if python_type is bool:
        return "Boolean"
    return python_type.__name__


def field_value(field, layer):
    from wntrqgis.elements import CurveType, InitialStatus, ModelLayer, PatternType

    python_type = field.python_type
    if issubclass(python_type, Enum):
        if python_type is InitialStatus and layer is ModelLayer.PIPES:
            enum_list = [InitialStatus.Open, InitialStatus.Closed]
        else:
            enum_list = python_type.__members__
        return ", ".join(enum_list)
    if issubclass(python_type, PatternType):
        return "Pattern"
    if issubclass(python_type, CurveType):
        return "Curve"
    if field.name in ["NAME", "LENGTH"]:
        return "Will calculate if blank"


def field_analysis_type(field):
    from wntrqgis.elements import FieldGroup

    analysis_types_of_interest = [
        FieldGroup.PRESSURE_DEPENDENT_DEMAND,
        FieldGroup.ENERGY,
        FieldGroup.WATER_QUALITY_ANALYSIS,
    ]
    return ", ".join([g.name.title().replace("_", " ") for g in analysis_types_of_interest if g in field.field_group])


def setup(app):
    app.connect("builder-inited", generate_attributes_table)
