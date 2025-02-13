from qgis.core import QgsProcessingProvider

from wntrqgis.resource_manager import WqIcon
from wntrqgis.wntrqgis_processing.empty_model import TemplateLayers
from wntrqgis.wntrqgis_processing.import_inp import ImportInp
from wntrqgis.wntrqgis_processing.run_simulation import RunSimulation
from wntrqgis.wntrqgis_processing.settings import SettingsAlgorithm


class Provider(QgsProcessingProvider):
    def __init__(self) -> None:
        super().__init__()

        self._id = "wntr"
        self._name = "WNTR"

    def id(self) -> str:
        return self._id

    def name(self) -> str:
        return self._name

    def load(self) -> bool:
        self.refreshAlgorithms()
        return True

    def icon(self):
        return WqIcon.LOGO.q_icon

    def loadAlgorithms(self) -> None:  # noqa N802
        self.addAlgorithm(RunSimulation())
        self.addAlgorithm(ImportInp())
        self.addAlgorithm(TemplateLayers())
        self.addAlgorithm(SettingsAlgorithm())
