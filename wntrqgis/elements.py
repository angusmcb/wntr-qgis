"""
Set of elements which describe parts of the network

Note:
    This module does not import WNTR, so can safely be run before checking if WNTR is installed.
"""

from __future__ import annotations

from enum import Enum, Flag, auto

from qgis.core import Qgis, QgsField, QgsFields, QgsProcessing, QgsWkbTypes
from qgis.PyQt.QtCore import QMetaType, QVariant

QGIS_VERSION_QMETATYPE = 33800


class FlowUnit(Enum):
    LPS = "Litres per Second"  # doc: Litres per second
    LPM = "Litres per Minute"  # doc: Litres per minute
    MLD = "Mega Litres Per Day"
    CMH = "Cubic Metres per Hour"
    CFS = "Cubic Feet per Second"
    GPM = "Gallons per Minute"
    MGD = "Mega Gallons per Day"
    IMGD = "Imperial Mega Gallons per Day"
    AFD = "Acre-feet per Day"
    SI = "International System of Units (SI)"


class HeadlossFormula(Enum):
    HAZEN_WILLIAMS = "H-W"
    DARCY_WEISBACH = "D-W"
    CHEZY_MANNING = "C-M"

    @property
    def friendly_name(self):
        return self.name.replace("_", " ").title()


class PumpTypes(str, Enum):
    POWER = "POWER"
    HEAD = "HEAD"


class InitialStatus(str, Enum):
    OPEN = "Open"
    CLOSED = "Closed"


class ValveType(str, Enum):
    PRV = "Pressure Reducing Valve"
    PSV = "Pressure Sustaining Valve"
    PBV = "Pressure Breaking Valve"
    FCV = "Flow Control Valve"
    TCV = "Throttle Control Valve"
    GPV = "General Purpose Valve"


class FieldGroup(Flag):
    BASE = auto()
    WATER_QUALITY_ANALYSIS = auto()
    PRESSURE_DEPENDENT_DEMAND = auto()
    ENERGY = auto()
    EXTRA = auto()
    REQUIRED = auto()


class ElementFamily(Enum):
    """Enum for node and link types"""

    NODE = auto()
    LINK = auto()


class LayerType(Flag):
    JUNCTIONS = auto()
    RESERVOIRS = auto()
    TANKS = auto()
    PIPES = auto()
    PUMPS = auto()
    VALVES = auto()
    NODES = JUNCTIONS | RESERVOIRS | TANKS
    LINKS = PIPES | PUMPS | VALVES
    ALL = NODES | LINKS

    @property
    def friendly_name(self):
        return self.name.title()

    @property
    def qgs_wkb_type(self):
        return QgsWkbTypes.Point if self in LayerType.NODES else QgsWkbTypes.LineString

    @property
    def acceptable_processing_vectors(self):
        return [QgsProcessing.TypeVectorPoint] if self in LayerType.NODES else [QgsProcessing.TypeVectorLine]


class _AbstractLayer(str, Enum):
    """Abstract enum for layer enums"""

    @property
    def friendly_name(self):
        return self.value.title()

    @property
    def qgs_wkb_type(self):
        return QgsWkbTypes.Point if self.element_family is ElementFamily.NODE else QgsWkbTypes.LineString


class ModelLayer(_AbstractLayer):
    JUNCTIONS = "JUNCTIONS"
    RESERVOIRS = "RESERVOIRS"
    TANKS = "TANKS"
    PIPES = "PIPES"
    PUMPS = "PUMPS"
    VALVES = "VALVES"

    @property
    def element_family(self) -> ElementFamily:
        """Layer is a node or a link?"""
        return (
            ElementFamily.NODE
            if self in [ModelLayer.JUNCTIONS, ModelLayer.RESERVOIRS, ModelLayer.TANKS]
            else ElementFamily.LINK
        )

    @property
    def acceptable_processing_vectors(self):
        return (
            [QgsProcessing.TypeVectorPoint]
            if self.element_family is ElementFamily.NODE
            else [QgsProcessing.TypeVectorLine]
        )

    def wq_fields(self, field_group: FieldGroup | None = None) -> list[ModelField]:
        """Mapping of fields associated with each layer"""

        field_dict = {
            ModelLayer.JUNCTIONS: [
                ModelField.NAME,
                ModelField.ELEVATION,
                ModelField.BASE_DEMAND,
                ModelField.DEMAND_PATTERN,
                ModelField.EMITTER_COEFFICIENT,
                ModelField.INITIAL_QUALITY,
                ModelField.MINIMUM_PRESSURE,
                ModelField.REQUIRED_PRESSURE,
                ModelField.PRESSURE_EXPONENT,
            ],
            ModelLayer.TANKS: [
                ModelField.NAME,
                ModelField.ELEVATION,
                ModelField.INIT_LEVEL,
                ModelField.MIN_LEVEL,
                ModelField.MAX_LEVEL,
                ModelField.DIAMETER,
                ModelField.MIN_VOL,
                ModelField.VOL_CURVE,
                ModelField.OVERFLOW,
                ModelField.INITIAL_QUALITY,
                ModelField.MIXING_FRACTION,
                ModelField.MIXING_MODEL,
                ModelField.BULK_COEFF,
            ],
            ModelLayer.RESERVOIRS: [
                ModelField.NAME,
                ModelField.BASE_HEAD,
                ModelField.HEAD_PATTERN,
                ModelField.INITIAL_QUALITY,
            ],
            ModelLayer.PIPES: [
                ModelField.NAME,
                ModelField.LENGTH,
                ModelField.DIAMETER,
                ModelField.ROUGHNESS,
                ModelField.MINOR_LOSS,
                ModelField.INITIAL_STATUS,
                ModelField.CHECK_VALVE,
                ModelField.BULK_COEFF,
                ModelField.WALL_COEFF,
            ],
            ModelLayer.PUMPS: [
                ModelField.NAME,
                ModelField.PUMP_TYPE,
                ModelField.PUMP_CURVE,
                ModelField.POWER,
                ModelField.BASE_SPEED,
                ModelField.SPEED_PATTERN,
                ModelField.INITIAL_STATUS,
                ModelField.INITIAL_SETTING,
                ModelField.EFFICIENCY,
                ModelField.ENERGY_PATTERN,
                ModelField.ENERGY_PRICE,
            ],
            ModelLayer.VALVES: [
                ModelField.NAME,
                ModelField.DIAMETER,
                ModelField.VALVE_TYPE,
                ModelField.MINOR_LOSS,
                ModelField.INITIAL_STATUS,
                ModelField.INITIAL_SETTING,
            ],
        }
        field_list = field_dict[self]
        if field_group:
            return [field for field in field_list if field.field_group & field_group]
        return field_list

    def qgs_fields(self, analysis_type: FieldGroup) -> QgsFields:
        """QgsFields object of fields associated with each layer"""
        qgs_fields = QgsFields()
        field_list = self.wq_fields(analysis_type)
        for field in field_list:
            qgs_fields.append(field.qgs_field)
        return qgs_fields


class ResultLayer(_AbstractLayer):
    NODES = "OUTPUTNODES"
    LINKS = "OUTPUTLINKS"

    @property
    def element_family(self):
        return ElementFamily.NODE if self is ResultLayer.NODES else ElementFamily.LINK

    def wq_fields(self):
        if self is ResultLayer.NODES:
            return [
                ResultField.DEMAND,
                ResultField.HEAD,
                ResultField.PRESSURE,
                ResultField.QUALITY,
            ]
        return [
            ResultField.FLOWRATE,
            ResultField.HEADLOSS,
            ResultField.VELOCITY,
        ]


class _AbstractField(Enum):
    def __new__(cls, *args):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, *args):
        self._python_type = args[1]
        self._field_group = args[2]

    @property
    def python_type(self) -> type:
        """The expected python type"""
        return self._python_type

    @property
    def field_group(self) -> FieldGroup:
        """The field group(s) the field is part of"""
        return self._field_group

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


class ModelField(_AbstractField):
    """All recognised fields that could be in a model layer"""

    NAME = "name", str, FieldGroup.BASE
    ELEVATION = "elevation", float, FieldGroup.BASE
    BASE_DEMAND = "base_demand", float, FieldGroup.BASE
    DEMAND_PATTERN = "demand_pattern", str, FieldGroup.BASE
    EMITTER_COEFFICIENT = "emitter_coefficient", float, FieldGroup.BASE
    INIT_LEVEL = "init_level", float, FieldGroup.BASE | FieldGroup.REQUIRED
    MIN_LEVEL = "min_level", float, FieldGroup.BASE | FieldGroup.REQUIRED
    MAX_LEVEL = "max_level", float, FieldGroup.BASE | FieldGroup.REQUIRED
    VALVE_TYPE = "valve_type", ValveType, FieldGroup.BASE | FieldGroup.REQUIRED
    DIAMETER = "diameter", float, FieldGroup.BASE | FieldGroup.REQUIRED
    MIN_VOL = "min_vol", float, FieldGroup.BASE
    VOL_CURVE = "vol_curve", str, FieldGroup.BASE
    OVERFLOW = "overflow", bool, FieldGroup.BASE
    BASE_HEAD = "base_head", float, FieldGroup.BASE
    HEAD_PATTERN = "head_pattern", str, FieldGroup.BASE
    LENGTH = "length", float, FieldGroup.BASE
    ROUGHNESS = "roughness", float, FieldGroup.BASE | FieldGroup.REQUIRED
    MINOR_LOSS = "minor_loss", float, FieldGroup.BASE
    INITIAL_STATUS = "initial_status", InitialStatus, FieldGroup.BASE
    CHECK_VALVE = "check_valve", bool, FieldGroup.BASE
    PUMP_TYPE = "pump_type", PumpTypes, FieldGroup.BASE | FieldGroup.REQUIRED
    PUMP_CURVE = "pump_curve", str, FieldGroup.BASE
    POWER = "power", float, FieldGroup.BASE
    BASE_SPEED = "base_speed", float, FieldGroup.BASE
    SPEED_PATTERN = "speed_pattern", str, FieldGroup.BASE
    INITIAL_SETTING = "initial_setting", float, FieldGroup.BASE

    INITIAL_QUALITY = "initial_quality", float, FieldGroup.WATER_QUALITY_ANALYSIS
    MIXING_FRACTION = "mixing_fraction", float, FieldGroup.WATER_QUALITY_ANALYSIS
    MIXING_MODEL = "mixing_model", float, FieldGroup.WATER_QUALITY_ANALYSIS
    BULK_COEFF = "bulk_coeff", float, FieldGroup.WATER_QUALITY_ANALYSIS
    WALL_COEFF = "wall_coeff", float, FieldGroup.WATER_QUALITY_ANALYSIS

    MINIMUM_PRESSURE = "minimum_pressure", float, FieldGroup.PRESSURE_DEPENDENT_DEMAND
    REQUIRED_PRESSURE = "required_pressure", float, FieldGroup.PRESSURE_DEPENDENT_DEMAND
    PRESSURE_EXPONENT = "pressure_exponent", float, FieldGroup.PRESSURE_DEPENDENT_DEMAND

    EFFICIENCY = "efficiency", str, FieldGroup.ENERGY
    ENERGY_PATTERN = "emergy_pattern", float, FieldGroup.ENERGY
    ENERGY_PRICE = "energy_price", float, FieldGroup.ENERGY

    @property
    def qgs_field(self):
        return QgsField(self.name.lower(), self._qgs_wkb_type)


class ResultField(_AbstractField):
    """Fields that can be in the results layers"""

    DEMAND = "demand", float, FieldGroup.BASE
    HEAD = "head", float, FieldGroup.BASE
    PRESSURE = "pressure", float, FieldGroup.BASE
    QUALITY = "quality", float, FieldGroup.WATER_QUALITY_ANALYSIS

    FLOWRATE = "flowrate", float, FieldGroup.BASE
    HEADLOSS = "headloss", float, FieldGroup.BASE
    VELOCITY = "velocity", float, FieldGroup.BASE

    @property
    def qgs_field(self):
        return QgsField(self.name.lower(), self._get_qgs_field_type(list), subType=self._qgs_wkb_type)
