Installation
============

This plugin requires QGIS 3.34 or greater. If not already installed QGIS installers are [downloadable from their website](https://www.qgis.org/download/).

Install the plugin from the plugin repository within QGIS in the normal way. See the [QGIS Manual](https://docs.qgis.org/latest/en/docs/training_manual/qgis_plugins/fetching_plugins.html) if necessary.

If the WNTR python package is not already installed in the QGIS python environment, it will be installed within the plugin directory when first running the tools.

WNTR itself has some python dependencies. A warning will appear when running any of the algorithms from the 'processing toolbox' if there are missing dependencies.
* On *Windows* all dependencies are already included within QGIS.
* For *Linux / Mac* you will need to ensure that the following python packages are installed: Numpy, Scipy, Pandas, NetworkX,  Matplotlib and Geopandas. Exactly how to do this depends on your system and how you have installed QGIS.


![](../_static/install.gif)
