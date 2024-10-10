from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from wntrqgis.qgis_plugin_tools.tools.resources import resources_path
from wntrqgis.wntrqgis_processing.empty_model import TemplateLayers
from wntrqgis.wntrqgis_processing.import_inp import ImportInp
from wntrqgis.wntrqgis_processing.run_simulation import RunSimulation


class Provider(QgsProcessingProvider):
    def __init__(self) -> None:
        super().__init__()

        self._id = "wntr"
        self._name = "WNTR"

    def id(self) -> str:
        return self._id

    def name(self) -> str:
        """
        The display name of your plugin in Processing.

        This string should be as short as possible and localised.
        """
        return self._name

    def load(self) -> bool:
        self.refreshAlgorithms()
        return True

    def icon(self):
        return QIcon(resources_path("icons", "water_circle.jpg"))

    def loadAlgorithms(self) -> None:  # noqa N802
        """
        Adds individual processing algorithms to the provider.
        """
        self.addAlgorithm(RunSimulation())
        self.addAlgorithm(ImportInp())
        self.addAlgorithm(TemplateLayers())
