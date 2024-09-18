import os
from pathlib import Path

import processing
from qgis.core import *


def get_example(name):
    return str(Path(__file__) / "wntrqgis" / "resources" / "examples" / name)


class MyFeedBack(QgsProcessingFeedback):
    def setProgressText(self, text):
        print(text)

    def pushInfo(self, info):
        print(info)

    def pushCommandInfo(self, info):
        print(info)

    def pushDebugInfo(self, info):
        print(info)

    def pushConsoleInfo(self, info):
        print(info)

    def reportError(self, error, fatalError=False):
        print(error)


def refreshprocessing():
    QgsApplication.processingRegistry().providerById("script").refreshAlgorithms()


def buildandrun():
    refreshprocessing()
    return processing.runAndLoadResults(
        "script:run",
        {
            "INPUT": "C:\\Users\\amcbride\\Downloads\\boujdour avec patterns.inp",
            "INPUTNODES": "C:/Users/amcbride/Downloads/epanettestnetwork.gpkg|layername=nodes",
            "INPUTLINKS": "C:/Users/amcbride/Downloads/epanettestnetwork.gpkg|layername=links",
            "OUTPUTNODES": "TEMPORARY_OUTPUT",
            "OUTPUTLINKS": "TEMPORARY_OUTPUT",
        },
        feedback=MyFeedBack(),
    )


def importinp():
    refreshprocessing()
    alg_params = {
        "CRS": QgsCoordinateReferenceSystem("EPSG:32629"),
        "INPUT": str(Path(__file__).parent / "resources" / "examples" / "Net1.inp"),
        "OUTPUTLINKS": "TEMPORARY_OUTPUT",
        "OUTPUTNODES": "TEMPORARY_OUTPUT",
    }
    return processing.runAndLoadResults("wntr:importinp", alg_params, feedback=MyFeedBack())


def buildandrunerror():
    refreshprocessing()
    return processing.runAndLoadResults(
        "script:run",
        {
            "INPUT": "C:\\Users\\amcbride\\Downloads\\boujdour avec patterns.inp",
            "INPUTNODES": "C:/Users/amcbride/Downloads/epanettestnetwork.gpkg|layername=nodes",
            "INPUTLINKS": "C:/Users/amcbride/Downloads/epanettestnetwork - error.gpkg|layername=links",
            "OUTPUTNODES": "TEMPORARY_OUTPUT",
            "OUTPUTLINKS": "TEMPORARY_OUTPUT",
        },
        feedback=MyFeedBack(),
    )


def impexample3():
    refreshprocessing()
    alg_params = {
        "CRS": QgsCoordinateReferenceSystem("EPSG:32629"),
        "INPUT": "C:\\Users\\amcbride\\GIS\\wntr_integration/WNTR-main/examples/networks/Net3.inp",
        "OUTPUTLINKS": "TEMPORARY_OUTPUT",
        "OUTPUTNODES": "TEMPORARY_OUTPUT",
    }
    return processing.runAndLoadResults("script:importinp", alg_params, feedback=MyFeedBack())


def impexample2():
    refreshprocessing()
    alg_params = {
        "CRS": QgsCoordinateReferenceSystem("EPSG:32629"),
        "INPUT": "C:\\Users\\amcbride\\GIS\\wntr_integration/WNTR-main/examples/networks/Net2.inp",
        "OUTPUTLINKS": "TEMPORARY_OUTPUT",
        "OUTPUTNODES": "TEMPORARY_OUTPUT",
    }
    return processing.runAndLoadResults("script:importinp", alg_params, feedback=MyFeedBack())
