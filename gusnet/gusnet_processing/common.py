from __future__ import annotations  # noqa
from contextlib import contextmanager
import functools
from typing import ClassVar, TYPE_CHECKING
from enum import Enum
import logging


from qgis.core import (
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingContext,
    QgsProcessingAlgorithm,
    QgsVectorLayer,
    QgsApplication,
)

from qgis.PyQt.QtCore import QCoreApplication, QThread
from gusnet.elements import ModelLayer, ResultLayer
from gusnet.settings import SettingKey, ProjectSettings
from gusnet.style import style
from gusnet.i18n import tr
from gusnet.units import SpecificUnitNames

if TYPE_CHECKING:  # pragma: no cover
    import wntr
LOGGER = logging.getLogger("gusnet")

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


class CommonProcessingBase(QgsProcessingAlgorithm):
    post_processors: ClassVar[dict[str, QgsProcessingLayerPostProcessorInterface]] = {}

    def helpUrl(self) -> str:  # noqa: N802
        return "https://www.gusnet.org"

    def postProcessAlgorithm(self, context, feedback):  # noqa: N802
        if QThread.currentThread() == QCoreApplication.instance().thread() and hasattr(self, "_settings"):
            project_settings = ProjectSettings()
            for setting_key, setting_value in self._settings.items():
                project_settings.set(setting_key, setting_value)

        return super().postProcessAlgorithm(context, feedback)

    def canExecute(self):  # noqa: N802
        try:
            import wntr  # noqa: F401
        except ImportError:
            msg = tr("WNTR cannot be loaded. Please wait a minute then try again, or consult our help site.")
            return False, msg

        return True, ""

    def _check_wntr(self) -> None:
        can_execute, message = self.canExecute()
        if not can_execute:
            raise QgsProcessingException(message)

    def _describe_model(self, wn: wntr.network.model.WaterNetworkModel, feedback: QgsProcessingFeedback) -> None:
        feedback.pushInfo(tr("WNTR model created. Model contains:"))
        feedback.pushInfo(str(wn.describe(level=0)))

    def _setup_postprocessing(self, context: QgsProcessingContext, outputs: dict, group_name: str, *args, **kwargs):
        output_order = [
            ModelLayer.JUNCTIONS,
            ModelLayer.PIPES,
            ModelLayer.PUMPS,
            ModelLayer.VALVES,
            ModelLayer.RESERVOIRS,
            ModelLayer.TANKS,
        ]

        for layer_type, lyr_id in outputs.items():
            if not context.willLoadLayerOnCompletion(lyr_id):
                continue

            self.post_processors[lyr_id] = ModelLayerPostProcessor(layer_type, *args, **kwargs)

            layer_details = context.layerToLoadOnCompletionDetails(lyr_id)
            layer_details.setPostProcessor(self.post_processors[lyr_id])
            layer_details.groupName = group_name
            layer_details.layerSortKey = output_order.index(layer_type)


class ModelLayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    def __init__(
        self,
        layer_type: ModelLayer | ResultLayer,
        make_editable: bool = False,  # noqa: FBT001, FBT002
        unit_names: SpecificUnitNames | None = None,
    ):
        super().__init__()
        self.layer_type = layer_type
        self.make_editable = make_editable
        self.unit_names = unit_names

    def postProcessLayer(self, layer: QgsVectorLayer, context, feedback) -> None:  # noqa N802 ARG002
        style(layer, self.layer_type, None, self.unit_names)

        project_settings = ProjectSettings()
        wntr_layers = project_settings.get(SettingKey.MODEL_LAYERS, {})
        wntr_layers[self.layer_type.name] = layer.id()
        project_settings.set(SettingKey.MODEL_LAYERS, wntr_layers)

        if self.make_editable:
            layer.startEditing()


PROFILER_GROUP_NAME = "Gusnet"


@contextmanager
def profile(name: str, percentage: int | None = None, feedback: QgsProcessingFeedback | None = None):
    """
    Context manager to profile a block of code in processing.
    """

    if feedback and feedback.isCanceled():
        raise QgsProcessingException(tr("Execution of script cancelled by user"))

    if feedback:
        feedback.setProgressText(name)
        # this is to ensure that feedback goes to min 5% straight away rather than waiting at 100
        feedback.setProgress(feedback.progress() + 5)

    qgs_profiler = QgsApplication.profiler()
    qgs_profiler.start(name, PROFILER_GROUP_NAME)

    try:
        yield functools.partial(profile, feedback=feedback)

        if feedback and percentage:
            feedback.setProgress(percentage)
    finally:
        qgs_profiler.end(PROFILER_GROUP_NAME)
