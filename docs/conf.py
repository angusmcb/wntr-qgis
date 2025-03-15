# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import subprocess
import sys

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


# -- Custom code to generate attributes table ------------------------------
def generate_attributes_table():
    from wntrqgis.elements import FieldGroup, ModelField, ModelLayer

    table_template = """
.. table:: Possible {layer_name} Layer Attributes

    +---------------------+------------------------------+
    | Attribute           | If not set                   |
    +=====================+==============================+
{rows}
"""

    row_template = (
        "    | {attribute:<19} | {default:<28} |\n    +---------------------+------------------------------+\n"
    )

    tables = []
    for layer in ModelLayer:
        rows = []
        for field in layer.wq_fields():
            default = "*Required*" if FieldGroup.REQUIRED in field.field_group else "None"
            rows.append(row_template.format(attribute=field.name.lower(), default=default))
        table = table_template.format(layer_name=layer.name.capitalize(), rows="".join(rows))
        tables.append(table)

    return "\n".join(tables)


def run_generate_attributes_table_script(app):
    output_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "user_guide/creating_the_model.rst"))
    with open(output_file) as file:
        content = file.readlines()

    start_marker = ".. AUTO-GENERATED-ATTRIBUTES-TABLE-START\n"
    end_marker = ".. AUTO-GENERATED-ATTRIBUTES-TABLE-END\n"

    start_index = content.index(start_marker) + 1
    end_index = content.index(end_marker)

    generated_table = generate_attributes_table()

    new_content = content[:start_index] + [generated_table] + content[end_index:]

    with open(output_file, "w") as file:
        file.writelines(new_content)


def setup(app):
    app.connect("builder-inited", run_generate_attributes_table_script)
