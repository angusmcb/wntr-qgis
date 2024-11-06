from __future__ import annotations  # noqa
from typing import ClassVar, TYPE_CHECKING
from pathlib import Path
from enum import IntEnum
import logging

import time
from qgis.core import (
    QgsProcessingLayerPostProcessorInterface,
    QgsVectorLayer,
    QgsProcessingException,
    QgsProcessingFeedback,
)
from qgis.PyQt.QtCore import QCoreApplication
from wntrqgis.dependency_management import WqDependencyManagemet
from wntrqgis.network_parts import WqProjectVar

if TYPE_CHECKING:
    import wntr
LOGGER = logging.getLogger("wntrqgis")


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None
    layertype = None
    group_name = None
    make_editable = None

    def postProcessLayer(self, layer, context, feedback):  # noqa N802 ARG002
        if not isinstance(layer, QgsVectorLayer):
            return
        layer.loadNamedStyle(str(Path(__file__).parent.parent / "resources" / "styles" / (self.layertype + ".qml")))
        wntr_layers = WqProjectVar.INLAYERS.get()
        if not isinstance(wntr_layers, dict):
            wntr_layers = {}
        wntr_layers[self.layertype] = layer.id()
        WqProjectVar.INLAYERS.set(wntr_layers)

        if self.group_name:
            project = context.project()
            root_group = project.layerTreeRoot()
            if not root_group.findGroup(self.group_name):
                root_group.insertGroup(0, self.group_name)
            group1 = root_group.findGroup(self.group_name)
            lyr_node = root_group.findLayer(layer.id())
            if lyr_node:
                node_clone = lyr_node.clone()
                group1.addChildNode(node_clone)
                lyr_node.parent().removeChildNode(lyr_node)

        if self.make_editable:
            layer.startEditing()

    @staticmethod
    def create(layertype: str, group_name="", make_editable=False) -> LayerPostProcessor:  # noqa FBT002
        LayerPostProcessor.instance = LayerPostProcessor()
        LayerPostProcessor.instance.layertype = layertype
        LayerPostProcessor.instance.group_name = group_name
        LayerPostProcessor.instance.make_editable = make_editable
        return LayerPostProcessor.instance


class ProgStatus(IntEnum):
    CHECKING_DEPENDENCIES = 5
    UNPACKING_WNTR = 7
    PREPARING_MODEL = 15
    RUNNING_SIMULATION = 40
    CREATING_OUTPUTS = 70
    FINISHED_PROCESSING = 95

    LOADING_INP_FILE = 10

    def __str__(self):
        return self.name.replace("_", " ").title()


class WntrQgisProcessingBase:
    post_processors: ClassVar[dict[str, LayerPostProcessor]] = {}

    def processAlgorithm(self, parameters, context, feedback):  # noqa N802
        if feedback is None:
            feedback = QgsProcessingFeedback()
        self.feedback = feedback

        self.start_time = time.perf_counter()
        self.last_time = self.start_time
        self.last_progress = None

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("Processing", string)

    def _update_progress(self, prog_status: ProgStatus) -> None:
        time_now = time.perf_counter()
        elapsed_ms = (time_now - self.last_time) * 1000
        if self.last_progress:
            self.feedback.pushDebugInfo(f"{self.last_progress} took {elapsed_ms:.0f}ms")
        self.last_time = time_now
        self.last_progress = prog_status

        self.feedback.setProgress(prog_status.value)
        self.feedback.setProgressText(self.tr(str(prog_status)))

    def _describe_model(self, wn: wntr.network.model.WaterNetworkModel) -> None:
        self.feedback.pushInfo(self.tr("WNTR model created. Model contains:"))
        self.feedback.pushInfo(str(wn.describe(level=0)))

    def _check_and_unpack_dependencies(self) -> None:
        self._update_progress(ProgStatus.CHECKING_DEPENDENCIES)

        if WqDependencyManagemet.check_dependencies():
            msg = "Missing Dependencies"
            raise QgsProcessingException(msg)

        if WqDependencyManagemet.check_wntr() is None:
            self._update_progress(ProgStatus.UNPACKING_WNTR)
            WqDependencyManagemet.install_wntr()