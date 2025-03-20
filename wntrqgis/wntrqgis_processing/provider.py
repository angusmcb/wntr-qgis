from qgis.core import QgsProcessingProvider

from wntrqgis.resource_manager import WqIcon
from wntrqgis.wntrqgis_processing.empty_model import TemplateLayers
from wntrqgis.wntrqgis_processing.import_inp import ImportInp
from wntrqgis.wntrqgis_processing.run_simulation import RunSimulation
from wntrqgis.wntrqgis_processing.settings import SettingsAlgorithm


class Provider(QgsProcessingProvider):
    def id(self) -> str:
        return "wntr"

    def name(self) -> str:
        return "WNTR"

    def icon(self):
        return WqIcon.LOGO.q_icon

    def loadAlgorithms(self) -> None:  # noqa N802
        self.addAlgorithm(RunSimulation())
        self.addAlgorithm(ImportInp())
        self.addAlgorithm(TemplateLayers())
        self.addAlgorithm(SettingsAlgorithm())
