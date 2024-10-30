from __future__ import annotations  # noqa
from typing import ClassVar
from pathlib import Path
from enum import IntEnum
from qgis.core import (
    QgsProcessingLayerPostProcessorInterface,
    QgsVectorLayer,
    QgsProcessingException,
)
from qgis.PyQt.QtCore import QCoreApplication
from wntrqgis.dependency_management import WqDependencyManagemet
from wntrqgis.utilswithoutwntr import WqUtil, WqProjectVar


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None
    layertype = None

    def postProcessLayer(self, layer, context, feedback):  # noqa N802 ARG002
        if not isinstance(layer, QgsVectorLayer):
            return
        layer.loadNamedStyle(str(Path(__file__).parent.parent / "resources" / "styles" / (self.layertype + ".qml")))
        wntr_layers = WqUtil.get_project_var(WqProjectVar.INLAYERS)
        if wntr_layers is None:
            wntr_layers = {}
        wntr_layers[self.layertype] = layer.id()
        WqUtil.set_project_var(WqProjectVar.INLAYERS, wntr_layers)

    @staticmethod
    def create(layertype) -> LayerPostProcessor:
        LayerPostProcessor.instance = LayerPostProcessor()
        LayerPostProcessor.instance.layertype = layertype
        return LayerPostProcessor.instance


class ProgStatus(IntEnum):
    CHECKING_DEPENDENCIES = 5
    UNPACKING_WNTR = 7
    PREPARING_MODEL = 10
    RUNNING_SIMULATION = 25
    SIMULATION_COMPLETED = 50
    PREPARING_NODE_OUTPUT = 55
    PREPARING_LINK_OUTPUT = 80
    FINISHED_PROCESSING = 95

    LOADING_INP_FILE = 10
    CREATING_OUTPUTS = 45

    def __str__(self):
        return self.name.replace("_", " ").title()


class WntrQgisProcessingBase:
    post_processors: ClassVar[dict[str, LayerPostProcessor]] = {}

    def tr(self, string) -> str:
        return QCoreApplication.translate("Processing", string)

    def _update_progress(self, feedback, prog_status):
        if prog_status in ProgStatus:
            feedback.setProgress(prog_status.value)
            feedback.setProgressText(self.tr(str(prog_status)))

    def _describe_model(self, feedback, wn):
        feedback.pushInfo(self.tr("WNTR model created. Model contains:"))
        feedback.pushInfo(str(wn.describe(level=0)))

    def _check_and_unpack_dependencies(self, feedback):
        self._update_progress(feedback, ProgStatus.CHECKING_DEPENDENCIES)

        if WqDependencyManagemet.check_dependencies():
            msg = "Missing Dependencies"
            raise QgsProcessingException(msg)

        if WqDependencyManagemet.check_wntr() is None:
            self._update_progress(feedback, ProgStatus.UNPACKING_WNTR)
            WqDependencyManagemet.install_wntr()
