from __future__ import annotations

from enum import Enum, Flag, auto
from typing import Any

from qgis.core import Qgis, QgsExpressionContextUtils, QgsField, QgsFields, QgsProcessing, QgsProject, QgsWkbTypes
from qgis.PyQt.QtCore import QMetaType, QVariant

QGIS_VERSION_QMETATYPE = 33800


class WqFlowUnit(Enum):
    LPS = "Litres per Second"
    LPM = "Litres per Minute"
    MLD = "Mega Litres Per Day"
    CMH = "Cubic Metres per Hour"
    CFS = "Cubic Feet per Second"
    GPM = "Gallons per Minute"
    MGD = "Mega Gallons per Day"
    IMGD = "Imperial Mega Gallons per Day"
    AFD = "Acre-feet per Day"
    SI = "International System of Units (SI)"


class WqHeadlossFormula(Enum):
    HAZEN_WILLIAMS = "H-W"
    DARCY_WEISBACH = "D-W"
    CHEZY_MANNING = "C-M"

    @property
    def friendly_name(self):
        return self.name.replace("_", " ").title()


class WqCurve(Enum):
    HEAD = "HEAD"
    EFFICIENCY = "EFFICIENCY"
    VOLUME = "VOLUME"
    HEADLOSS = "HEADLOSS"


class WqPumpTypes(str, Enum):
    POWER = "POWER"
    HEAD = "HEAD"


class WqInitialStatus(str, Enum):
    OPEN = "Open"
    CLOSED = "Closed"


class WqValveType(str, Enum):
    PRV = "Pressure Reducing Valve"
    PSV = "Pressure Sustaining Valve"
    PBV = "Pressure Breaking Valve"
    FCV = "Flow Control Valve"
    TCV = "Throttle Control Valve"
    GPV = "General Purpose Valve"


class WqAnalysisType(Flag):
    BASE = auto()
    QUALITY = auto()
    PDA = auto()
    ENERGY = auto()
    NOOUTPUT = auto()
    REQUIRED = auto()


class WqElementFamily(Enum):
    """Enum for node and link types"""

    NODE = auto()
    LINK = auto()


class WqLayer(str, Enum):
    """Abstract enum for layer enums"""

    @property
    def friendly_name(self):
        return self.value.title()

    @property
    def qgs_wkb_type(self):
        return QgsWkbTypes.Point if self.element_family is WqElementFamily.NODE else QgsWkbTypes.LineString


class WqResultLayer(WqLayer):
    NODES = "OUTPUTNODES"
    LINKS = "OUTPUTLINKS"

    @property
    def element_family(self):
        return WqElementFamily.NODE if self is WqResultLayer.NODES else WqElementFamily.LINK

    @property
    def wntr_attr(self):
        return "node" if self is WqResultLayer.NODES else "link"

    @property
    def wq_fields(self):
        if self is WqResultLayer.NODES:
            return [
                WqResultField.DEMAND,
                WqResultField.HEAD,
                WqResultField.PRESSURE,
                WqResultField.QUALITY,
            ]
        return [
            WqResultField.FLOWRATE,
            WqResultField.HEADLOSS,
            WqResultField.VELOCITY,
        ]


class WqModelLayer(WqLayer):
    JUNCTIONS = "JUNCTIONS"
    RESERVOIRS = "RESERVOIRS"
    TANKS = "TANKS"
    PIPES = "PIPES"
    PUMPS = "PUMPS"
    VALVES = "VALVES"

    @property
    def wntr_attr(self):
        return self.value.lower()

    @property
    def element_family(self):
        """Layer is a node or a link?"""
        return (
            WqElementFamily.NODE
            if self in [WqModelLayer.JUNCTIONS, WqModelLayer.RESERVOIRS, WqModelLayer.TANKS]
            else WqElementFamily.LINK
        )

    @property
    def acceptable_processing_vectors(self):
        """List of acceptable vector types for processing interface"""
        return (
            [QgsProcessing.TypeVectorPoint]
            if self.element_family is WqElementFamily.NODE
            else [QgsProcessing.TypeVectorLine]
        )

    @property
    def node_link_type(self):
        """This will be used for fixing bug in WNTR 1.2.0"""
        return str(self).title()[:-1]

    def wq_fields(self, analysis_type=None):
        """Fields associated with each layer"""
        field_list = []
        # if self.is_node:
        #     field_list = [
        #         WqModelField.NAME,
        #         WqModelField.INITIAL_QUALITY,
        #     ]
        # else:
        #     field_list = [
        #         WqModelField.NAME,
        #         # WqModelField.START_NODE_NAME,
        #         # WqModelField.END_NODE_NAME,
        #     ]
        field_dict = {
            WqModelLayer.JUNCTIONS: [
                WqModelField.NAME,
                WqModelField.ELEVATION,
                WqModelField.BASE_DEMAND,
                WqModelField.DEMAND_PATTERN,
                WqModelField.EMITTER_COEFFICIENT,
                WqModelField.INITIAL_QUALITY,
                WqModelField.MINIMUM_PRESSURE,
                WqModelField.REQUIRED_PRESSURE,
                WqModelField.PRESSURE_EXPONENT,
            ],
            WqModelLayer.TANKS: [
                WqModelField.NAME,
                WqModelField.ELEVATION,
                WqModelField.INIT_LEVEL,
                WqModelField.MIN_LEVEL,
                WqModelField.MAX_LEVEL,
                WqModelField.DIAMETER,
                WqModelField.MIN_VOL,
                WqModelField.VOL_CURVE,
                WqModelField.OVERFLOW,
                WqModelField.INITIAL_QUALITY,
                WqModelField.MIXING_FRACTION,
                WqModelField.MIXING_MODEL,
                WqModelField.BULK_COEFF,
            ],
            WqModelLayer.RESERVOIRS: [
                WqModelField.NAME,
                WqModelField.BASE_HEAD,
                WqModelField.HEAD_PATTERN,
                WqModelField.INITIAL_QUALITY,
            ],
            WqModelLayer.PIPES: [
                WqModelField.NAME,
                # WqModelField.START_NODE_NAME,
                # WqModelField.END_NODE_NAME,
                WqModelField.LENGTH,
                WqModelField.DIAMETER,
                WqModelField.ROUGHNESS,
                WqModelField.MINOR_LOSS,
                WqModelField.INITIAL_STATUS,
                WqModelField.CHECK_VALVE,
                WqModelField.BULK_COEFF,
                WqModelField.WALL_COEFF,
            ],
            WqModelLayer.PUMPS: [
                WqModelField.NAME,
                # WqModelField.START_NODE_NAME,
                # WqModelField.END_NODE_NAME,
                WqModelField.PUMP_TYPE,
                WqModelField.PUMP_CURVE,
                WqModelField.POWER,
                WqModelField.BASE_SPEED,
                WqModelField.SPEED_PATTERN,
                WqModelField.INITIAL_STATUS,
                WqModelField.INITIAL_SETTING,
                WqModelField.EFFICIENCY,
                WqModelField.ENERGY_PATTERN,
                WqModelField.ENERGY_PRICE,
            ],
            WqModelLayer.VALVES: [
                WqModelField.NAME,
                # WqModelField.START_NODE_NAME,
                # WqModelField.END_NODE_NAME,
                WqModelField.DIAMETER,
                WqModelField.VALVE_TYPE,
                WqModelField.MINOR_LOSS,
                WqModelField.INITIAL_STATUS,
                WqModelField.INITIAL_SETTING,
            ],
        }

        # match self:
        #     case WqModelLayer.JUNCTIONS:
        #         field_list = [
        #             WqModelField.NAME,
        #             WqModelField.ELEVATION,
        #             WqModelField.BASE_DEMAND,
        #             WqModelField.DEMAND_PATTERN,
        #             WqModelField.EMITTER_COEFFICIENT,
        #             WqModelField.INITIAL_QUALITY,
        #             WqModelField.MINIMUM_PRESSURE,
        #             WqModelField.REQUIRED_PRESSURE,
        #             WqModelField.PRESSURE_EXPONENT,
        #         ]
        #     case WqModelLayer.TANKS:
        #         field_list = [
        #             WqModelField.NAME,
        #             WqModelField.ELEVATION,
        #             WqModelField.INIT_LEVEL,
        #             WqModelField.MIN_LEVEL,
        #             WqModelField.MAX_LEVEL,
        #             WqModelField.DIAMETER,
        #             WqModelField.MIN_VOL,
        #             WqModelField.VOL_CURVE,
        #             WqModelField.OVERFLOW,
        #             WqModelField.INITIAL_QUALITY,
        #             WqModelField.MIXING_FRACTION,
        #             WqModelField.MIXING_MODEL,
        #             WqModelField.BULK_COEFF,
        #         ]
        #     case WqModelLayer.RESERVOIRS:
        #         field_list = [
        #             WqModelField.NAME,
        #             WqModelField.BASE_HEAD,
        #             WqModelField.HEAD_PATTERN,
        #             WqModelField.INITIAL_QUALITY,
        #         ]
        #     case WqModelLayer.PIPES:
        #         field_list = [
        #             WqModelField.NAME,
        #             # WqModelField.START_NODE_NAME,
        #             # WqModelField.END_NODE_NAME,
        #             WqModelField.LENGTH,
        #             WqModelField.DIAMETER,
        #             WqModelField.ROUGHNESS,
        #             WqModelField.MINOR_LOSS,
        #             WqModelField.INITIAL_STATUS,
        #             WqModelField.CHECK_VALVE,
        #             WqModelField.BULK_COEFF,
        #             WqModelField.WALL_COEFF,
        #         ]
        #     case WqModelLayer.PUMPS:
        #         field_list = [
        #             WqModelField.NAME,
        #             # WqModelField.START_NODE_NAME,
        #             # WqModelField.END_NODE_NAME,
        #             WqModelField.PUMP_TYPE,
        #             WqModelField.PUMP_CURVE,
        #             WqModelField.POWER,
        #             WqModelField.BASE_SPEED,
        #             WqModelField.SPEED_PATTERN,
        #             WqModelField.INITIAL_STATUS,
        #             WqModelField.INITIAL_SETTING,
        #             WqModelField.EFFICIENCY,
        #             WqModelField.ENERGY_PATTERN,
        #             WqModelField.ENERGY_PRICE,
        #         ]
        #     case WqModelLayer.VALVES:
        #         field_list = [
        #             WqModelField.NAME,
        #             # WqModelField.START_NODE_NAME,
        #             # WqModelField.END_NODE_NAME,
        #             WqModelField.DIAMETER,
        #             WqModelField.VALVE_TYPE,
        #             WqModelField.MINOR_LOSS,
        #             WqModelField.INITIAL_STATUS,
        #             WqModelField.INITIAL_SETTING,
        #         ]
        #     case _:
        #         raise KeyError
        field_list = field_dict[self]
        if analysis_type:
            return [field for field in field_list if field.analysis_type & analysis_type]
        return field_list

    def qgs_fields(self, analysis_type: WqAnalysisType):
        qgs_fields = QgsFields()
        field_list = self.wq_fields(analysis_type)
        for field in field_list:
            qgs_fields.append(field.qgs_field)
        return qgs_fields


class WqField(Enum):
    def __new__(cls, *args):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, *args):
        self._python_type = args[1]
        self._analysis_type = args[2]

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):  # noqa ARG004
        return name.lower()

    @property
    def python_type(self):
        return self._python_type

    @property
    def analysis_type(self):
        return self._analysis_type

    @property
    def _qgs_wkb_type(self):
        return self._get_qgs_field_type(self.python_type)

    def _get_qgs_field_type(self, python_type):
        use_qmetatype = Qgis.versionInt() >= QGIS_VERSION_QMETATYPE

        if issubclass(python_type, str):
            return QMetaType.QString if use_qmetatype else QVariant.String
        if issubclass(python_type, float):
            return QMetaType.Double if use_qmetatype else QVariant.Double
        if issubclass(python_type, bool):
            return QMetaType.Bool if use_qmetatype else QVariant.Bool
        if issubclass(python_type, int):
            return QMetaType.Int if use_qmetatype else QVariant.Int
        if issubclass(python_type, list):
            return QMetaType.QVariantList if use_qmetatype else QVariant.List

        raise KeyError


class WqModelField(WqField):
    @property
    def qgs_field(self):
        return QgsField(self.name.lower(), self._qgs_wkb_type)

    NAME = "name", str, WqAnalysisType.BASE
    # START_NODE_NAME = object(), str, WqAnalysisType.NOOUTPUT
    # END_NODE_NAME = object(), str, WqAnalysisType.NOOUTPUT
    ELEVATION = "elevation", float, WqAnalysisType.BASE
    BASE_DEMAND = "base_demand", float, WqAnalysisType.BASE
    DEMAND_PATTERN = "demand_pattern", str, WqAnalysisType.BASE
    EMITTER_COEFFICIENT = "emitter_coefficient", float, WqAnalysisType.BASE
    INIT_LEVEL = "init_level", float, WqAnalysisType.BASE | WqAnalysisType.REQUIRED
    MIN_LEVEL = "min_level", float, WqAnalysisType.BASE | WqAnalysisType.REQUIRED
    MAX_LEVEL = "max_level", float, WqAnalysisType.BASE | WqAnalysisType.REQUIRED
    DIAMETER = "diameter", float, WqAnalysisType.BASE | WqAnalysisType.REQUIRED
    MIN_VOL = "min_vol", float, WqAnalysisType.BASE
    VOL_CURVE = "vol_curve", str, WqAnalysisType.BASE
    OVERFLOW = "overflow", bool, WqAnalysisType.BASE
    BASE_HEAD = "base_head", float, WqAnalysisType.BASE
    HEAD_PATTERN = "head_pattern", str, WqAnalysisType.BASE
    LENGTH = "length", float, WqAnalysisType.BASE
    ROUGHNESS = "roughness", float, WqAnalysisType.BASE | WqAnalysisType.REQUIRED
    MINOR_LOSS = "minor_loss", float, WqAnalysisType.BASE
    INITIAL_STATUS = "initial_status", WqInitialStatus, WqAnalysisType.BASE
    CHECK_VALVE = "check_valve", bool, WqAnalysisType.BASE
    PUMP_TYPE = "pump_type", WqPumpTypes, WqAnalysisType.BASE | WqAnalysisType.REQUIRED
    PUMP_CURVE = "pump_curve", str, WqAnalysisType.BASE
    POWER = "power", float, WqAnalysisType.BASE
    BASE_SPEED = "base_speed", float, WqAnalysisType.BASE
    SPEED_PATTERN = "speed_pattern", str, WqAnalysisType.BASE
    INITIAL_SETTING = "initial_setting", float, WqAnalysisType.BASE
    VALVE_TYPE = "valve_type", WqValveType, WqAnalysisType.BASE | WqAnalysisType.REQUIRED

    INITIAL_QUALITY = "initial_quality", float, WqAnalysisType.QUALITY
    MIXING_FRACTION = "mixing_fraction", float, WqAnalysisType.QUALITY
    MIXING_MODEL = "mixing_model", float, WqAnalysisType.QUALITY
    BULK_COEFF = "bulk_coeff", float, WqAnalysisType.QUALITY
    WALL_COEFF = "wall_coeff", float, WqAnalysisType.QUALITY

    MINIMUM_PRESSURE = "minimum_pressure", float, WqAnalysisType.PDA
    REQUIRED_PRESSURE = "required_pressure", float, WqAnalysisType.PDA
    PRESSURE_EXPONENT = "pressure_exponent", float, WqAnalysisType.PDA

    EFFICIENCY = "efficiency", str, WqAnalysisType.ENERGY
    ENERGY_PATTERN = "emergy_pattern", float, WqAnalysisType.ENERGY
    ENERGY_PRICE = "energy_price", float, WqAnalysisType.ENERGY


class WqResultField(WqField):
    @property
    def qgs_field(self):
        return QgsField(self.name.lower(), self._get_qgs_field_type(list), subType=self._qgs_wkb_type)

    DEMAND = "demand", float, WqAnalysisType.BASE
    HEAD = "head", float, WqAnalysisType.BASE
    PRESSURE = "pressure", float, WqAnalysisType.BASE
    QUALITY = "quality", float, WqAnalysisType.QUALITY

    FLOWRATE = "flowrate", float, WqAnalysisType.BASE
    HEADLOSS = "headloss", float, WqAnalysisType.BASE
    VELOCITY = "velocity", float, WqAnalysisType.BASE


class WqProjectSetting(str, Enum):
    """Enum of values that can be stored in project settings"""

    OPTIONS = "options", dict
    FLOW_UNITS = "flow_units", WqFlowUnit
    CONTROLS = "controls", str
    MODEL_LAYERS = "model_layers", dict
    HEADLOSS_FORMULA = "headloss_formula", WqHeadlossFormula
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
