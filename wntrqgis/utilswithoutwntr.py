from enum import Enum, Flag, StrEnum, auto
from typing import Any

from qgis.core import Qgis, QgsExpressionContextUtils, QgsField, QgsFields, QgsProcessing, QgsProject, QgsWkbTypes
from qgis.PyQt.QtCore import QMetaType, QVariant

QGIS_VERSION_QMETATYPE = 33800


class WqProjectVar(StrEnum):
    OPTIONS = "wntr_options"
    FLOW_UNITS = "wntr_flow_units"
    CONTROLS = "wntr_controls"
    INLAYERS = "wntr_inlayers"


# Used for namespae
class WqUtil:
    @staticmethod
    def set_project_var(projectvariable: WqProjectVar, value: Any):
        QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(), projectvariable.value, value)

    @staticmethod
    def get_project_var(projectvariable: WqProjectVar):
        return QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable(projectvariable.value)

    @staticmethod
    def get_qgs_field_type(python_type):
        newstyle = Qgis.versionInt() >= QGIS_VERSION_QMETATYPE

        if python_type is str:
            return QMetaType.QString if newstyle else QVariant.String
        if python_type is float:
            return QMetaType.Double if newstyle else QVariant.Double
        if python_type is bool:
            return QMetaType.Bool if newstyle else QVariant.Bool
        if python_type is int:
            return QMetaType.Int if newstyle else QVariant.Int
        if python_type is list:
            return QMetaType.QVariantList if newstyle else QVariant.List

        raise KeyError


class WqFlowUnit(StrEnum):
    LPS = auto()
    LPM = auto()
    MLD = auto()
    CMH = auto()
    CFS = auto()
    GPM = auto()
    MGD = auto()
    IMGD = auto()
    AFD = auto()
    SI = auto()


class WqAnalysisType(Flag):
    BASE = auto()
    QUALITY = auto()
    PDA = auto()
    ENERGY = auto()


class WqLayer(StrEnum):
    @property
    def friendly_name(self):
        return self.value.title()

    @property
    def qgs_wkb_type(self):
        return QgsWkbTypes.Point if self.is_node else QgsWkbTypes.LineString


class WqOutLayer(WqLayer):
    NODES = "OUTPUTNODES"
    LINKS = "OUTPUTLINKS"

    @property
    def is_node(self):
        return self is WqOutLayer.NODES

    @property
    def wntr_attr(self):
        return "node" if self is WqOutLayer.NODES else "link"

    @property
    def wq_fields(self):
        wq_fields = []
        match self:
            case WqOutLayer.NODES:
                wq_fields = [
                    WqOutField.DEMAND,
                    WqOutField.HEAD,
                    WqOutField.PRESSURE,
                    WqOutField.QUALITY,
                ]
            case WqOutLayer.LINKS:
                wq_fields = [
                    WqOutField.FLOWRATE,
                    WqOutField.HEADLOSS,
                    WqOutField.VELOCITY,
                ]
            case _:
                raise KeyError
        return wq_fields


class WqInLayer(WqLayer):
    JUNCTIONS = "JUNCTIONS"
    RESERVOIRS = "RESERVOIRS"
    TANKS = "TANKS"
    PIPES = "PIPES"
    PUMPS = "PUMPS"
    VALVES = "VALVES"

    @property
    def is_node(self):
        return self in [WqInLayer.JUNCTIONS, WqInLayer.RESERVOIRS, WqInLayer.TANKS]

    @property
    def wntr_attr(self):
        return self.value.lower()

    @property
    def acceptable_processing_vectors(self):
        return [QgsProcessing.TypeVectorPoint] if self.is_node else [QgsProcessing.TypeVectorLine]

    # This will be used for fixing bug in WNTR 1.2.0
    @property
    def node_link_type(self):
        return str(self).title()[:-1]

    def wq_fields(self, analysis_type: WqAnalysisType):
        field_list = []
        match self:
            case WqInLayer.JUNCTIONS:
                field_list = [
                    WqInField.NAME,
                    WqInField.ELEVATION,
                    WqInField.BASE_DEMAND,
                    WqInField.DEMAND_PATTERN,
                    WqInField.EMITTER_COEFFICIENT,
                    WqInField.INITIAL_QUALITY,
                    WqInField.MINIMUM_PRESSURE,
                    WqInField.REQUIRED_PRESSURE,
                    WqInField.PRESSURE_EXPONENT,
                ]
            case WqInLayer.TANKS:
                field_list = [
                    WqInField.NAME,
                    WqInField.ELEVATION,
                    WqInField.INIT_LEVEL,
                    WqInField.MIN_LEVEL,
                    WqInField.MAX_LEVEL,
                    WqInField.DIAMETER,
                    WqInField.MIN_VOL,
                    WqInField.VOL_CURVE,
                    WqInField.OVERFLOW,
                    WqInField.INITIAL_QUALITY,
                    WqInField.MIXING_FRACTION,
                    WqInField.MIXING_MODEL,
                    WqInField.BULK_COEFF,
                ]
            case WqInLayer.RESERVOIRS:
                field_list = [
                    WqInField.NAME,
                    WqInField.BASE_HEAD,
                    WqInField.HEAD_PATTERN,
                    WqInField.INITIAL_QUALITY,
                ]
            case WqInLayer.PIPES:
                field_list = [
                    WqInField.NAME,
                    WqInField.START_NODE_NAME,
                    WqInField.END_NODE_NAME,
                    WqInField.LENGTH,
                    WqInField.DIAMETER,
                    WqInField.ROUGHNESS,
                    WqInField.MINOR_LOSS,
                    WqInField.INITIAL_STATUS,
                    WqInField.CHECK_VALVE,
                    WqInField.BULK_COEFF,
                    WqInField.WALL_COEFF,
                ]
            case WqInLayer.PUMPS:
                field_list = [
                    WqInField.NAME,
                    WqInField.START_NODE_NAME,
                    WqInField.END_NODE_NAME,
                    WqInField.PUMP_TYPE,
                    WqInField.PUMP_CURVE,
                    WqInField.POWER,
                    WqInField.BASE_SPEED,
                    WqInField.SPEED_PATTERN,
                    WqInField.INITIAL_STATUS,
                    WqInField.INITIAL_SETTING,
                    WqInField.EFFICIENCY,
                    WqInField.ENERGY_PATTERN,
                    WqInField.ENERGY_PRICE,
                ]
            case WqInLayer.VALVES:
                field_list = [
                    WqInField.NAME,
                    WqInField.START_NODE_NAME,
                    WqInField.END_NODE_NAME,
                    WqInField.DIAMETER,
                    WqInField.VALVE_TYPE,
                    WqInField.MINOR_LOSS,
                    WqInField.INITIAL_STATUS,
                    WqInField.INITIAL_SETTING,
                ]
            case _:
                raise KeyError

        return [field for field in field_list if field.analysis_type in analysis_type]

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

    def __init__(self, _, python_type, analysis_type):
        self._python_type = python_type
        self._analysis_type = analysis_type

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
        return WqUtil.get_qgs_field_type(self.python_type)


class WqInField(WqField):
    @property
    def qgs_field(self):
        return QgsField(self.value, self._qgs_wkb_type)

    NAME = auto(), str, WqAnalysisType.BASE
    ELEVATION = auto(), float, WqAnalysisType.BASE
    BASE_DEMAND = auto(), float, WqAnalysisType.BASE
    DEMAND_PATTERN = auto(), str, WqAnalysisType.BASE
    EMITTER_COEFFICIENT = auto(), float, WqAnalysisType.BASE
    INIT_LEVEL = auto(), float, WqAnalysisType.BASE
    MIN_LEVEL = auto(), float, WqAnalysisType.BASE
    MAX_LEVEL = auto(), float, WqAnalysisType.BASE
    DIAMETER = auto(), float, WqAnalysisType.BASE
    MIN_VOL = auto(), float, WqAnalysisType.BASE
    VOL_CURVE = auto(), str, WqAnalysisType.BASE
    OVERFLOW = auto(), bool, WqAnalysisType.BASE
    BASE_HEAD = auto(), float, WqAnalysisType.BASE
    HEAD_PATTERN = auto(), str, WqAnalysisType.BASE
    START_NODE_NAME = auto(), str, WqAnalysisType.BASE
    END_NODE_NAME = auto(), str, WqAnalysisType.BASE
    LENGTH = auto(), float, WqAnalysisType.BASE
    ROUGHNESS = auto(), float, WqAnalysisType.BASE
    MINOR_LOSS = auto(), float, WqAnalysisType.BASE
    INITIAL_STATUS = auto(), str, WqAnalysisType.BASE
    CHECK_VALVE = auto(), bool, WqAnalysisType.BASE
    PUMP_TYPE = auto(), str, WqAnalysisType.BASE
    PUMP_CURVE = auto(), str, WqAnalysisType.BASE
    POWER = auto(), float, WqAnalysisType.BASE
    BASE_SPEED = auto(), float, WqAnalysisType.BASE
    SPEED_PATTERN = auto(), str, WqAnalysisType.BASE
    INITIAL_SETTING = auto(), float, WqAnalysisType.BASE
    VALVE_TYPE = auto(), str, WqAnalysisType.BASE

    INITIAL_QUALITY = auto(), float, WqAnalysisType.QUALITY
    MIXING_FRACTION = auto(), float, WqAnalysisType.QUALITY
    MIXING_MODEL = auto(), float, WqAnalysisType.QUALITY
    BULK_COEFF = auto(), float, WqAnalysisType.QUALITY
    WALL_COEFF = auto(), float, WqAnalysisType.QUALITY

    MINIMUM_PRESSURE = auto(), float, WqAnalysisType.PDA
    REQUIRED_PRESSURE = auto(), float, WqAnalysisType.PDA
    PRESSURE_EXPONENT = auto(), float, WqAnalysisType.PDA

    EFFICIENCY = auto(), float, WqAnalysisType.ENERGY
    ENERGY_PATTERN = auto(), float, WqAnalysisType.ENERGY
    ENERGY_PRICE = auto(), float, WqAnalysisType.ENERGY


class WqOutField(WqField):
    @property
    def qgs_field(self):
        return QgsField(self.value, WqUtil.get_qgs_field_type(list), subType=self._qgs_wkb_type)

    DEMAND = auto(), float, WqAnalysisType.BASE
    HEAD = auto(), float, WqAnalysisType.BASE
    PRESSURE = auto(), float, WqAnalysisType.BASE
    QUALITY = auto(), float, WqAnalysisType.QUALITY

    FLOWRATE = auto(), float, WqAnalysisType.BASE
    HEADLOSS = auto(), float, WqAnalysisType.BASE
    VELOCITY = auto(), float, WqAnalysisType.BASE
