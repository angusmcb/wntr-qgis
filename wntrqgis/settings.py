from __future__ import annotations

from enum import Enum
from typing import Any

from qgis.core import QgsExpressionContextUtils, QgsProject

from wntrqgis.network_parts import FlowUnit, HeadlossFormula


class WqProjectSetting(str, Enum):
    """Enum of values that can be stored in project settings"""

    OPTIONS = "options", dict
    FLOW_UNITS = "flow_units", FlowUnit
    CONTROLS = "controls", str
    MODEL_LAYERS = "model_layers", dict
    HEADLOSS_FORMULA = "headloss_formula", HeadlossFormula
    SIMULATION_DURATION = "simulation_duration", float

    def __new__(cls, *args):
        obj = str.__new__(cls, [args[0]])
        obj._value_ = args[0]
        return obj

    def __init__(self, *args):
        self.expected_type = args[1]

    # @property
    # def _setting_name(self):
    #     return SETTING_PREFIX + self.name.lower()

    # def set(self, value: Any):
    #     if not isinstance(value, self.value[1]):
    #         msg = f"{self.name} expects to save types {type(self.value[1])} but got {type(value)}"
    #         raise TypeError(msg)
    #     QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(), self._setting_name, value)

    # def get(self, default_value=None):
    #     saved_value = QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable(self._setting_name)
    #     if isinstance(saved_value, self.value[1]):
    #         return saved_value
    #     return default_value


class WqProjectSettings:
    """Gets and sets WNTR project settings"""

    SETTING_PREFIX = "wntr_"

    def __init__(self, project: QgsProject):
        self._project = project

    def _setting_name(self, setting):
        """Adds the setting prefix to the setting name"""
        return self.SETTING_PREFIX + setting.value

    def get(self, setting: WqProjectSetting, default: Any | None = None):
        """Get a value from project settings, with optional default value"""
        setting_name = self._setting_name(setting)
        saved_value = QgsExpressionContextUtils.projectScope(self._project).variable(setting_name)
        if not saved_value:
            return default
        return setting.expected_type(saved_value)

    def set(self, setting: WqProjectSetting, value: Any):
        """Save a value to project settings"""
        setting_name = self._setting_name(setting)
        if not issubclass(type(value), setting.expected_type):
            msg = f"{setting} expects to save types {type(setting.expected_type)} but got {type(value)}"
            raise TypeError(msg)

        if isinstance(value, Enum):
            value = value.value

        QgsExpressionContextUtils.setProjectVariable(self._project, setting_name, value)
