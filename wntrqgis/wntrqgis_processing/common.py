from __future__ import annotations  # noqa
from typing import ClassVar, TYPE_CHECKING, Any
from enum import Enum
import logging

import time
from qgis.core import (
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingContext,
)

from wntrqgis.dependency_management import WntrInstaller, WntrInstallError
from wntrqgis.elements import ModelLayer, ResultLayer
from wntrqgis.settings import SettingKey, ProjectSettings
from wntrqgis.style import style
from wntrqgis.i18n import tr

if TYPE_CHECKING:  # pragma: no cover
    import wntr
LOGGER = logging.getLogger("wntrqgis")


class Progression(Enum):
    def __new__(cls, *args):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, *args):
        self.friendly_name = args[1]

    CHECKING_DEPENDENCIES = 5, tr("Checking dependencies")
    INSTALLING_WNTR = 15, tr("Installing WNTR")
    PREPARING_MODEL = 25, tr("Preparing model")
    RUNNING_SIMULATION = 40, tr("Running simulation")
    CREATING_OUTPUTS = 70, tr("Creating outputs")
    FINISHED_PROCESSING = 95, tr("Finished processing")
    LOADING_INP_FILE = 10, tr("Loading inp file")


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

    def _update_progress(self, prog_status: Progression) -> None:
        if self.feedback.isCanceled():
            raise QgsProcessingException(tr("Execution of script cancelled by user"))

        time_now = time.perf_counter()
        elapsed_ms = (time_now - self.last_time) * 1000
        if self.last_progress:
            self.feedback.pushDebugInfo(f"{self.last_progress.friendly_name} took {elapsed_ms:.0f}ms")
        self.last_time = time_now
        self.last_progress = prog_status

        self.feedback.setProgress(prog_status.value)
        self.feedback.setProgressText(prog_status.friendly_name)

    def _describe_model(self, wn: wntr.network.model.WaterNetworkModel) -> None:
        self.feedback.pushInfo(tr("WNTR model created. Model contains:"))
        self.feedback.pushInfo(str(wn.describe(level=0)))

    def _ensure_wntr(self) -> None:
        self._update_progress(Progression.CHECKING_DEPENDENCIES)

        try:
            import wntr

            wntr_version = wntr.__version__
        except ImportError:
            self._update_progress(Progression.INSTALLING_WNTR)
            try:
                wntr_version = WntrInstaller.install_wntr()
            except WntrInstallError as e:
                raise QgsProcessingException(e) from e

        self.feedback.pushDebugInfo("WNTR version: " + wntr_version)

    def _setup_postprocessing(self, outputs: dict[ModelLayer | ResultLayer, str], group_name: str, *args, **kwargs):
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
            if self.context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor(layer_type, *args, **kwargs)

                layer_details = self.context.layerToLoadOnCompletionDetails(lyr_id)
                layer_details.setPostProcessor(self.post_processors[lyr_id])
                layer_details.groupName = group_name
                layer_details.layerSortKey = output_order.index(layer_type)


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    def __init__(
        self,
        layer_type: ModelLayer | ResultLayer,
        make_editable=False,
        style_theme=None,
        is_model_layer=True,
    ):
        super().__init__()
        self.layer_type = layer_type
        self.make_editable = make_editable
        self.style_theme = style_theme
        self.is_model_layer = is_model_layer

    def postProcessLayer(self, layer, context, feedback):  # noqa N802 ARG002
        style(layer, self.layer_type, self.style_theme)

        if self.is_model_layer:
            project_settings = ProjectSettings(context.project())
            wntr_layers = project_settings.get(SettingKey.MODEL_LAYERS, {})
            wntr_layers[self.layer_type.name] = layer.id()
            project_settings.set(SettingKey.MODEL_LAYERS, wntr_layers)

        if self.make_editable:
            layer.startEditing()
