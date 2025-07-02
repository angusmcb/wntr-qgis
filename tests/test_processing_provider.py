import pytest
from qgis.core import QgsProcessingProvider, QgsProcessingRegistry
from qgis.PyQt.QtGui import QIcon

from wntrqgis.wntrqgis_processing.provider import Provider


def test_processing_provider():
    assert isinstance(Provider(), QgsProcessingProvider)


def test_processing_provider_icon():
    assert isinstance(Provider().icon(), QIcon)


def test_processing_provider_name():
    assert Provider().name() == "WNTR"


def test_processing_provider_id():
    assert Provider().id() == "wntr"


@pytest.mark.parametrize("algorithm", ["importinp", "run", "templatelayers"])
def test_processing_alg_loaded(algorithm):
    provider = Provider()
    provider.refreshAlgorithms()
    assert provider.algorithm(algorithm)


def test_register_processing_provider():
    provider = Provider()
    registry = QgsProcessingRegistry()
    registry.addProvider(provider)
    assert provider in registry.providers()
    registry.removeProvider(provider)
