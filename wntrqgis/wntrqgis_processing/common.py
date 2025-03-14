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
from wntrqgis.elements import ModelLayer, ResultLayer
from wntrqgis.settings import SettingKey, ProjectSettings
from wntrqgis.style import style

if TYPE_CHECKING:  # pragma: no cover
    import wntr
LOGGER = logging.getLogger("wntrqgis")


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None
    layertype = None
    make_editable = None
    style_theme = None

    def postProcessLayer(self, layer, context, feedback):  # noqa N802 ARG002
        if not isinstance(layer, QgsVectorLayer):
            return

        style(layer, self.layertype, self.style_theme)

        project_settings = ProjectSettings(context.project())
        wntr_layers = project_settings.get(SettingKey.MODEL_LAYERS, {})
        wntr_layers[self.layertype] = layer.id()
        project_settings.set(SettingKey.MODEL_LAYERS, wntr_layers)

        if self.make_editable:
            layer.startEditing()

    @staticmethod
    def create(layertype: str, make_editable=False, style_theme=None) -> LayerPostProcessor:  # noqa FBT002
        LayerPostProcessor.instance = LayerPostProcessor()
        LayerPostProcessor.instance.layertype = layertype
        LayerPostProcessor.instance.make_editable = make_editable
        LayerPostProcessor.instance.style_theme = style_theme
        return LayerPostProcessor.instance


class Progression(IntEnum):
    CHECKING_DEPENDENCIES = 5
    INSTALLING_WNTR = 15
    PREPARING_MODEL = 25
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
        self.last_progress: Progression | None = None

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("Processing", string)

    def _update_progress(self, prog_status: Progression) -> None:
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
        self._update_progress(Progression.CHECKING_DEPENDENCIES)

        try:
            wntrversion = WqDependencyManagement.import_wntr()
        except ImportError as e:
            raise QgsProcessingException(e) from None

        if not wntrversion:
            self._update_progress(Progression.INSTALLING_WNTR)
            wntrversion = WqDependencyManagement.ensure_wntr()

        self.feedback.pushDebugInfo("WNTR version: " + wntrversion)

    def _setup_postprocessing(
        self,
        outputs: dict[str, str],
        group_name: str,
        make_editable: bool,  # noqa: FBT001
        style_theme: str | None = None,
    ):
        output_order: list[str] = [
            ModelLayer.JUNCTIONS,
            ModelLayer.PIPES,
            ModelLayer.PUMPS,
            ModelLayer.VALVES,
            ModelLayer.RESERVOIRS,
            ModelLayer.TANKS,
            ResultLayer.LINKS,
            ResultLayer.NODES,
        ]

        for layer_type, lyr_id in outputs.items():
            if self.context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(layer_type, make_editable, style_theme)

                layer_details = self.context.layerToLoadOnCompletionDetails(lyr_id)
                layer_details.setPostProcessor(self.post_processors[lyr_id])
                layer_details.groupName = self.tr(group_name)
                layer_details.layerSortKey = output_order.index(layer_type)
