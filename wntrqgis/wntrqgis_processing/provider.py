from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from wntrqgis.wntrqgis_processing.empty_model import TemplateLayers
from wntrqgis.wntrqgis_processing.import_inp import ImportInp
from wntrqgis.wntrqgis_processing.run_simulation import RunSimulation


class Provider(QgsProcessingProvider):
    def id(self) -> str:
        return "wntr"

    def name(self) -> str:
        return "WNTR"

    def icon(self):
        return QIcon("wntrqgis:logo.png")

    def loadAlgorithms(self) -> None:  # noqa N802
        self.addAlgorithm(RunSimulation())
        self.addAlgorithm(ImportInp())
        self.addAlgorithm(TemplateLayers())
