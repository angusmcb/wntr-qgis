<img src="https://raw.githubusercontent.com/usepa/wntr/main/documentation/_static/logo.jpg" width="375"> <img src="https://raw.githubusercontent.com/qgis/QGIS/master/images/README-md/main_logo.png" width="300">

# WNTR - QGIS Integration
![tests](https://github.com/angusmcb/wntr-qgis/workflows/Tests/badge.svg)
[![codecov.io](https://codecov.io/github/angusmcb/wntr-qgis/coverage.svg?branch=main)](https://codecov.io/github/angusmcb/wntr-qgis?branch=main)
![release](https://github.com/angusmcb/wntr-qgis/workflows/Release/badge.svg)

[![GPLv2 license](https://img.shields.io/badge/License-GPLv2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

This QGIS plugin integrates the US EPA's [Water Network Tools for Resiliance (WNTR)](https://usepa.github.io/WNTR/) with [QGIS](https://qgis.org/). It is compatible with and import/exports to, EPANET. WNTR can also use the EPANET solver.

The purpose of this plugin is to allow the preperation and visualisation of results of water network models within QGIS.

Compared to other QGIS water network modelling plugins, this plugin aims to be:
- Robust.
- Easy to use.
- Flexible.
- Integrate the power of QGIS. It aims to completement rather than replace features already within QGIS. Data can be manipulated with the standard QGIS tools, processing algorithms, and plugins.
- Automatable / programmable. Tools are exposed so as to be usable from python / PyQGIS

## Installation

Install the plugin in QGIS in the normal way (see the [QGIS Manual](https://docs.qgis.org/latest/en/docs/training_manual/qgis_plugins/fetching_plugins.html) if necessary).

The WNTR python package must also be installed. If it is not already installed, then WNTR will silenetly install a copy into the plugin directory..

WNTR itself has some dependencies. A warning will appear if they are not installed. On *Windows* all dependencies are included with QGIS. It should just work (unless you have used the advanced installer and not chosen 'qgis-full'). For *Linux / Mac* You will need to ensure that the following python packages are installed: Numpy, Scipy, Pandas, GeoPandas, NetworkX, and Matplotlib. Exactly how to do this depends on your system and how you have installed QGIS.

## Usage

### Key Principles

1. **Layer Creation** Layers can either be created empty or imported from EPANET files using the tools provided in the processing toolbox (or you can create them manually). All of the layers are optional - only create what you need.
	- Nodes:
		- Junctions
		- Reservoirs
		- Tanks
	- Links:
		- Pipes
		- Pumps
		- Valves

2. **Layer Editing.** The layers are normal QGIS layers and can be edited / modified / processed / styled / automated in the same ways as any other QGIS layer. In particular:
	- *Snapping tools* can be used when drawing the network to make sure that nodes and links connect.
	- *Pipe lengths* can be calculated automatically (this expression is added by default to new pipe layers).
	- *Elevations* can be added to nodes from other sources using either expressions or processing tools..
	- *External data sources* or any other layers can be used as background maps or data sources for drawing the network.

3. **Running the model.** The plugin will load your nodes, linkes, patterns, curves and options into WNTR and run the model It will then process the output into a new link and node layer containing all calculated results.

## Development

Create a virtual environment activate it and install needed dependencies with the following commands:
```console
python create_qgis_venv.py
.venv\Scripts\activate # On Linux and macOS run `source .venv\bin\activate`
pip install -r requirements-dev.txt
```

For more detailed development instructions see [development](docs/development.md).

### Testing the plugin on QGIS

A symbolic link / directory junction should be made to the directory containing the installed plugins pointing to the dev plugin package.

On Windows Command promt
```console
mklink /J %AppData%\QGIS\QGIS3\profiles\default\python\plugins\wntrqgis .\wntrqgis
```

On Windows PowerShell
```console
New-Item -ItemType SymbolicLink -Path ${env:APPDATA}\QGIS\QGIS3\profiles\default\python\plugins\wntrqgis -Value ${pwd}\wntrqgis
```

On Linux
```console
ln -s wntrqgis/ ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/wntrqgis
```

After that you should be able to enable the plugin in the QGIS Plugin Manager.

### VsCode setup

On VS Code use the workspace [wntr-qgis.code-workspace](wntr-qgis.code-workspace).
The workspace contains all the settings and extensions needed for development.

Select the Python interpreter with Command Palette (Ctrl+Shift+P). Select `Python: Select Interpreter` and choose
the one with the path `.venv\Scripts\python.exe`.

## License
This plugin is distributed under the terms of the [GNU General Public License, version 2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html) license.

See [LICENSE](LICENSE) for more information.
