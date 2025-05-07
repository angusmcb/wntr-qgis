from __future__ import annotations  # noqa
from typing import ClassVar, TYPE_CHECKING
from enum import Enum
import logging

import time
from qgis.core import (
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingContext,
    QgsProcessingAlgorithm,
)

from qgis.PyQt.QtCore import QCoreApplication, QThread
from wntrqgis.dependency_management import WntrInstaller, WntrInstallError
from wntrqgis.elements import ModelLayer, ResultLayer
from wntrqgis.settings import SettingKey, ProjectSettings
from wntrqgis.style import style
from wntrqgis.i18n import tr

if TYPE_CHECKING:  # pragma: no cover
    import wntr
LOGGER = logging.getLogger("wntrqgis")

SHOW_TIMING = False


class Progression(Enum):
    CHECKING_DEPENDENCIES = 5
    INSTALLING_WNTR = 15
    PREPARING_MODEL = 25
    RUNNING_SIMULATION = 40
    CREATING_OUTPUTS = 70
    FINISHED_PROCESSING = 95
    LOADING_INP_FILE = 10

    @property
    def friendly_name(self):
        if self is Progression.CHECKING_DEPENDENCIES:
            return tr("Checking dependencies")
        if self is Progression.INSTALLING_WNTR:
            return tr("Installing WNTR")
        if self is Progression.PREPARING_MODEL:
            return tr("Preparing model")
        if self is Progression.RUNNING_SIMULATION:
            return tr("Running simulation")
        if self is Progression.CREATING_OUTPUTS:
            return tr("Creating outputs")
        if self is Progression.FINISHED_PROCESSING:
            return tr("Finished processing")
        if self is Progression.LOADING_INP_FILE:
            return tr("Loading inp file")
        raise ValueError


class WntrQgisProcessingBase(QgsProcessingAlgorithm):
    post_processors: ClassVar[dict[str, LayerPostProcessor]] = {}

    def postProcessAlgorithm(self, context, feedback):  # noqa: N802
        if QThread.currentThread() == QCoreApplication.instance().thread() and hasattr(self, "_settings"):
            project_settings = ProjectSettings()
            for setting_key, setting_value in self._settings.items():
                project_settings.set(setting_key, setting_value)

        return super().postProcessAlgorithm(context, feedback)

    def _describe_model(self, wn: wntr.network.model.WaterNetworkModel, feedback: QgsProcessingFeedback) -> None:
        feedback.pushInfo(tr("WNTR model created. Model contains:"))
        feedback.pushInfo(str(wn.describe(level=0)))

    def _ensure_wntr(self, progress_tracker: ProgressTracker) -> None:
        progress_tracker.update_progress(Progression.CHECKING_DEPENDENCIES)

        try:
            import wntr

            wntr_version = wntr.__version__
        except ImportError:
            progress_tracker.update_progress(Progression.INSTALLING_WNTR)
            try:
                wntr_version = WntrInstaller.install_wntr()
            except WntrInstallError as e:
                raise QgsProcessingException(e) from e

        return wntr_version
        # feedback.pushDebugInfo("WNTR version: " + wntr_version)

    def _setup_postprocessing(self, context: QgsProcessingContext, outputs: dict, group_name: str, *args, **kwargs):
        output_order: list = [
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
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor(layer_type, *args, **kwargs)

                layer_details = context.layerToLoadOnCompletionDetails(lyr_id)
                layer_details.setPostProcessor(self.post_processors[lyr_id])
                layer_details.groupName = group_name
                layer_details.layerSortKey = output_order.index(layer_type)


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    def __init__(
        self,
        layer_type: ModelLayer | ResultLayer,
        make_editable=False,  # noqa: FBT002
        style_theme=None,
        is_model_layer=True,  # noqa: FBT002
    ):
        super().__init__()
        self.layer_type = layer_type
        self.make_editable = make_editable
        self.style_theme = style_theme
        self.is_model_layer = is_model_layer

    def postProcessLayer(self, layer, context, feedback):  # noqa N802 ARG002
        style(layer, self.layer_type, self.style_theme)

        if self.is_model_layer:
            project_settings = ProjectSettings()
            wntr_layers = project_settings.get(SettingKey.MODEL_LAYERS, {})
            wntr_layers[self.layer_type.name] = layer.id()
            project_settings.set(SettingKey.MODEL_LAYERS, wntr_layers)

        if self.make_editable:
            layer.startEditing()


class ProgressTracker:
    def __init__(self, feedback: QgsProcessingFeedback):
        self.feedback = feedback
        self.start_time = time.perf_counter()
        self.last_time = self.start_time
        self.last_progress: Progression | None = None

    def update_progress(self, prog_status: Progression) -> None:
        if self.feedback.isCanceled():
            raise QgsProcessingException(tr("Execution of script cancelled by user"))

        time_now = time.perf_counter()
        elapsed_ms = (time_now - self.last_time) * 1000
        if self.last_progress and SHOW_TIMING:
            self.feedback.pushDebugInfo(f"{self.last_progress.friendly_name} took {elapsed_ms:.0f}ms")
        self.last_time = time_now
        self.last_progress = prog_status

        self.feedback.setProgress(prog_status.value)
        self.feedback.setProgressText(prog_status.friendly_name)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.feedback.pushDebugInfo(f"Exception: {exc_val}")
        self.feedback.setProgress(100)
