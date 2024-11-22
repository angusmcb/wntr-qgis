from __future__ import annotations  # noqa
from typing import ClassVar, TYPE_CHECKING, Any
from enum import IntEnum
import logging

import time
from qgis.core import (
    QgsProcessingLayerPostProcessorInterface,
    QgsVectorLayer,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingContext,
)
from qgis.PyQt.QtCore import QCoreApplication
from wntrqgis.dependency_management import WqDependencyManagement
from wntrqgis.network_parts import WqProjectVar, WqModelLayer, WqResultLayer
from wntrqgis.layer_styles import WqLayerStyles

if TYPE_CHECKING:
    import wntr
LOGGER = logging.getLogger("wntrqgis")


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None
    layertype = None
    make_editable = None

    def postProcessLayer(self, layer, context, feedback):  # noqa N802 ARG002
        if not isinstance(layer, QgsVectorLayer):
            return

        styler = WqLayerStyles(self.layertype)
        styler.style_layer(layer)

        wntr_layers = WqProjectVar.INLAYERS.get({})
        wntr_layers[self.layertype] = layer.id()
        WqProjectVar.INLAYERS.set(wntr_layers)

        if self.make_editable:
            layer.startEditing()

    @staticmethod
    def create(layertype: str, make_editable=False) -> LayerPostProcessor:  # noqa FBT002
        LayerPostProcessor.instance = LayerPostProcessor()
        LayerPostProcessor.instance.layertype = layertype
        LayerPostProcessor.instance.make_editable = make_editable
        return LayerPostProcessor.instance


class ProgStatus(IntEnum):
    CHECKING_DEPENDENCIES = 5
    UNPACKING_WNTR = 12
    PREPARING_MODEL = 15
    RUNNING_SIMULATION = 40
    CREATING_OUTPUTS = 70
    FINISHED_PROCESSING = 95

    LOADING_INP_FILE = 10

    def __str__(self):
        return self.name.replace("_", " ").title()


class WntrQgisProcessingBase:
    post_processors: ClassVar[dict[str, LayerPostProcessor]] = {}

    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],  # noqa ARG002
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ):
        if feedback is None:
            feedback = QgsProcessingFeedback()
        self.feedback = feedback
        self.context = context

        self.start_time = time.perf_counter()
        self.last_time = self.start_time
        self.last_progress: ProgStatus | None = None

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("Processing", string)

    def _update_progress(self, prog_status: ProgStatus) -> None:
        if self.feedback.isCanceled():
            raise QgsProcessingException(self.tr("Execution of script cancelled by user"))

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

    def _ensure_wntr(self) -> None:
        self._update_progress(ProgStatus.CHECKING_DEPENDENCIES)

        try:
            wntrversion = WqDependencyManagement.ensure_wntr()
        except ImportError as e:
            raise QgsProcessingException(e) from None

        self.feedback.pushDebugInfo("WNTR version: " + wntrversion)

    def _setup_postprocessing(self, outputs: dict[str, str], group_name: str, make_editable: bool):  # noqa FBT01
        output_order: list[str] = [
            WqModelLayer.JUNCTIONS,
            WqModelLayer.PIPES,
            WqModelLayer.PUMPS,
            WqModelLayer.VALVES,
            WqModelLayer.RESERVOIRS,
            WqModelLayer.TANKS,
            WqResultLayer.LINKS,
            WqResultLayer.NODES,
        ]

        for layer_type, lyr_id in outputs.items():
            if self.context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(layer_type, make_editable)

                layer_details = self.context.layerToLoadOnCompletionDetails(lyr_id)
                layer_details.setPostProcessor(self.post_processors[lyr_id])
                layer_details.groupName = self.tr(group_name)
                layer_details.layerSortKey = output_order.index(layer_type)
