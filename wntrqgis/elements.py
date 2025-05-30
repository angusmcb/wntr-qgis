"""
Set of elements which describe parts of the network

Note:
    This module does not import WNTR, so can safely be run before checking if WNTR is installed.
"""

from __future__ import annotations

from enum import Enum, Flag, auto

from qgis.core import QgsProcessing, QgsWkbTypes

from wntrqgis.i18n import tr


class FlowUnit(Enum):
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

    @property
    def friendly_name(self):
        if self is FlowUnit.LPS:
            return tr("Litres per Second")
        if self is FlowUnit.LPM:
            return tr("Litres per Minute")
        if self is FlowUnit.MLD:
            return tr("Mega Litres Per Day")
        if self is FlowUnit.CMH:
            return tr("Cubic Metres per Hour")
        if self is FlowUnit.CFS:
            return tr("Cubic Feet per Second")
        if self is FlowUnit.GPM:
            return tr("Gallons per Minute")
        if self is FlowUnit.MGD:
            return tr("Mega Gallons per Day")
        if self is FlowUnit.IMGD:
            return tr("Imperial Mega Gallons per Day")
        if self is FlowUnit.AFD:
            return tr("Acre-feet per Day")
        if self is FlowUnit.SI:
            return tr("International System of Units (SI)")
        raise ValueError


class HeadlossFormula(Enum):
    HAZEN_WILLIAMS = "H-W"
    DARCY_WEISBACH = "D-W"
    CHEZY_MANNING = "C-M"

    @property
    def friendly_name(self):
        if self is HeadlossFormula.HAZEN_WILLIAMS:
            return tr("Hazen-Williams")
        if self is HeadlossFormula.DARCY_WEISBACH:
            return tr("Darcy-Weisbach")
        if self is HeadlossFormula.CHEZY_MANNING:
            return tr("Chezy-Manning")
        raise ValueError


class _AbstractValueMap(Enum):
    """Abstract enum for value maps"""

    @property
    def friendly_name(self):
        """To be implemented by subclasses"""


class PumpTypes(_AbstractValueMap):
    POWER = auto()
    HEAD = auto()

    @property
    def friendly_name(self):
        if self is PumpTypes.POWER:
            return tr("Power")
        if self is PumpTypes.HEAD:
            return tr("Head")
        raise ValueError


class InitialStatus(_AbstractValueMap):
    ACTIVE = auto()
    OPEN = auto()
    CLOSED = auto()

    @property
    def friendly_name(self):
        if self is InitialStatus.OPEN:
            return tr("Open")
        if self is InitialStatus.ACTIVE:
            return tr("Active")
        if self is InitialStatus.CLOSED:
            return tr("Closed")
        raise ValueError


class ValveType(_AbstractValueMap):
    PRV = auto()
    PSV = auto()
    PBV = auto()
    FCV = auto()
    TCV = auto()
    GPV = auto()

    @property
    def friendly_name(self):
        if self is ValveType.PRV:
            return tr("Pressure Reducing Valve")
        if self is ValveType.PSV:
            return tr("Pressure Sustaining Valve")
        if self is ValveType.PBV:
            return tr("Pressure Breaking Valve")
        if self is ValveType.FCV:
            return tr("Flow Control Valve")
        if self is ValveType.TCV:
            return tr("Throttle Control Valve")
        if self is ValveType.GPV:
            return tr("General Purpose Valve")
        raise ValueError


class FieldGroup(Flag):
    BASE = auto()
    WATER_QUALITY_ANALYSIS = auto()
    PRESSURE_DEPENDENT_DEMAND = auto()
    ENERGY = auto()
    EXTRA = auto()
    REQUIRED = auto()


class PatternType(str):
    __slots__ = ()


class CurveType(str):
    __slots__ = ()


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


class _AbstractLayer(Enum):
    """Abstract enum for layer enums"""

    @property
    def results_name(self):
        """Name of the layer in the results"""
        return "RESULT_" + self.name

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
    def field_type(self):
        if self is ModelLayer.JUNCTIONS:
            return "Junction"
        if self is ModelLayer.RESERVOIRS:
            return "Reservoir"
        if self is ModelLayer.TANKS:
            return "Tank"
        if self is ModelLayer.PIPES:
            return "Pipe"
        if self is ModelLayer.PUMPS:
            return "Pump"
        if self is ModelLayer.VALVES:
            return "Valve"
        msg = "Unknown model layer type"
        raise ValueError(msg)

    @property
    def friendly_name(self):
        if self is ModelLayer.JUNCTIONS:
            return tr("Junctions")
        if self is ModelLayer.RESERVOIRS:
            return tr("Reservoirs")
        if self is ModelLayer.TANKS:
            return tr("Tanks")
        if self is ModelLayer.PIPES:
            return tr("Pipes")
        if self is ModelLayer.PUMPS:
            return tr("Pumps")
        if self is ModelLayer.VALVES:
            return tr("Valves")
        raise ValueError

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

    def wq_fields(self) -> list[ModelField]:
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
                ModelField.HEADLOSS_CURVE,
            ],
        }
        return field_dict[self]


class ResultLayer(_AbstractLayer):
    NODES = "OUTPUTNODES"
    LINKS = "OUTPUTLINKS"

    @property
    def friendly_name(self):
        if self is ResultLayer.NODES:
            return tr("Nodes")
        if self is ResultLayer.LINKS:
            return tr("Links")
        raise ValueError

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
            ResultField.QUALITY,
            ResultField.REACTION_RATE,
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


class ModelField(_AbstractField):
    """All recognised fields that could be in a model layer"""

    NAME = "name", str, FieldGroup.BASE
    ELEVATION = "elevation", float, FieldGroup.BASE | FieldGroup.REQUIRED
    BASE_DEMAND = "base_demand", float, FieldGroup.BASE
    DEMAND_PATTERN = "demand_pattern", PatternType, FieldGroup.BASE
    EMITTER_COEFFICIENT = "emitter_coefficient", float, FieldGroup.BASE
    INIT_LEVEL = "init_level", float, FieldGroup.BASE | FieldGroup.REQUIRED
    MIN_LEVEL = "min_level", float, FieldGroup.BASE | FieldGroup.REQUIRED
    MAX_LEVEL = "max_level", float, FieldGroup.BASE | FieldGroup.REQUIRED
    VALVE_TYPE = "valve_type", ValveType, FieldGroup.BASE | FieldGroup.REQUIRED
    DIAMETER = "diameter", float, FieldGroup.BASE | FieldGroup.REQUIRED
    MIN_VOL = "min_vol", float, FieldGroup.BASE
    VOL_CURVE = "vol_curve", CurveType, FieldGroup.BASE
    OVERFLOW = "overflow", bool, FieldGroup.BASE
    BASE_HEAD = "base_head", float, FieldGroup.BASE | FieldGroup.REQUIRED
    HEAD_PATTERN = "head_pattern", PatternType, FieldGroup.BASE
    LENGTH = "length", float, FieldGroup.BASE
    ROUGHNESS = "roughness", float, FieldGroup.BASE | FieldGroup.REQUIRED
    MINOR_LOSS = "minor_loss", float, FieldGroup.BASE
    CHECK_VALVE = "check_valve", bool, FieldGroup.BASE
    PUMP_TYPE = "pump_type", PumpTypes, FieldGroup.BASE | FieldGroup.REQUIRED
    PUMP_CURVE = "pump_curve", CurveType, FieldGroup.BASE
    POWER = "power", float, FieldGroup.BASE
    BASE_SPEED = "base_speed", float, FieldGroup.BASE
    SPEED_PATTERN = "speed_pattern", PatternType, FieldGroup.BASE
    INITIAL_STATUS = "initial_status", InitialStatus, FieldGroup.BASE
    INITIAL_SETTING = "initial_setting", float, FieldGroup.BASE
    HEADLOSS_CURVE = "headloss_curve", CurveType, FieldGroup.BASE

    INITIAL_QUALITY = "initial_quality", float, FieldGroup.WATER_QUALITY_ANALYSIS
    MIXING_FRACTION = "mixing_fraction", float, FieldGroup.WATER_QUALITY_ANALYSIS
    MIXING_MODEL = "mixing_model", float, FieldGroup.WATER_QUALITY_ANALYSIS
    BULK_COEFF = "bulk_coeff", float, FieldGroup.WATER_QUALITY_ANALYSIS
    WALL_COEFF = "wall_coeff", float, FieldGroup.WATER_QUALITY_ANALYSIS

    MINIMUM_PRESSURE = "minimum_pressure", float, FieldGroup.PRESSURE_DEPENDENT_DEMAND
    REQUIRED_PRESSURE = "required_pressure", float, FieldGroup.PRESSURE_DEPENDENT_DEMAND
    PRESSURE_EXPONENT = "pressure_exponent", float, FieldGroup.PRESSURE_DEPENDENT_DEMAND

    EFFICIENCY = "efficiency", CurveType, FieldGroup.ENERGY
    ENERGY_PATTERN = "energy_pattern", PatternType, FieldGroup.ENERGY
    ENERGY_PRICE = "energy_price", float, FieldGroup.ENERGY

    @property
    def friendly_name(self):
        if self is ModelField.NAME:
            return tr("Name")
        if self is ModelField.ELEVATION:
            return tr("Elevation")
        if self is ModelField.BASE_DEMAND:
            return tr("Base Demand")
        if self is ModelField.DEMAND_PATTERN:
            return tr("Demand Pattern")
        if self is ModelField.EMITTER_COEFFICIENT:
            return tr("Emitter Coefficient")
        if self is ModelField.INIT_LEVEL:
            return tr("Initial Level")
        if self is ModelField.MIN_LEVEL:
            return tr("Minimum Level")
        if self is ModelField.MAX_LEVEL:
            return tr("Maximum Level")
        if self is ModelField.VALVE_TYPE:
            return tr("Valve Type")
        if self is ModelField.DIAMETER:
            return tr("Diameter")
        if self is ModelField.MIN_VOL:
            return tr("Minimum Volume")
        if self is ModelField.VOL_CURVE:
            return tr("Volume Curve")
        if self is ModelField.OVERFLOW:
            return tr("Overflow")
        if self is ModelField.BASE_HEAD:
            return tr("Base Head")
        if self is ModelField.HEAD_PATTERN:
            return tr("Head Pattern")
        if self is ModelField.LENGTH:
            return tr("Length")
        if self is ModelField.ROUGHNESS:
            return tr("Roughness")
        if self is ModelField.MINOR_LOSS:
            return tr("Minor Loss")
        if self is ModelField.CHECK_VALVE:
            return tr("Check Valve")
        if self is ModelField.PUMP_TYPE:
            return tr("Pump Type")
        if self is ModelField.PUMP_CURVE:
            return tr("Pump Curve")
        if self is ModelField.POWER:
            return tr("Power")
        if self is ModelField.BASE_SPEED:
            return tr("Base Speed")
        if self is ModelField.SPEED_PATTERN:
            return tr("Speed Pattern")
        if self is ModelField.INITIAL_STATUS:
            return tr("Initial Status")
        if self is ModelField.INITIAL_SETTING:
            return tr("Initial Setting")
        if self is ModelField.HEADLOSS_CURVE:
            return tr("Headloss Curve")
        if self is ModelField.INITIAL_QUALITY:
            return tr("Initial Quality")
        if self is ModelField.MIXING_FRACTION:
            return tr("Mixing Fraction")
        if self is ModelField.MIXING_MODEL:
            return tr("Mixing Model")
        if self is ModelField.BULK_COEFF:
            return tr("Bulk Coefficient")
        if self is ModelField.WALL_COEFF:
            return tr("Wall Coefficient")
        if self is ModelField.MINIMUM_PRESSURE:
            return tr("Minimum Pressure")
        if self is ModelField.REQUIRED_PRESSURE:
            return tr("Required Pressure")
        if self is ModelField.PRESSURE_EXPONENT:
            return tr("Pressure Exponent")
        if self is ModelField.EFFICIENCY:
            return tr("Efficiency")
        if self is ModelField.ENERGY_PATTERN:
            return tr("Energy Pattern")
        if self is ModelField.ENERGY_PRICE:
            return tr("Energy Price")
        raise ValueError


class ResultField(_AbstractField):
    """Fields that can be in the results layers"""

    DEMAND = "demand", float, FieldGroup.BASE
    HEAD = "head", float, FieldGroup.BASE
    PRESSURE = "pressure", float, FieldGroup.BASE

    FLOWRATE = "flowrate", float, FieldGroup.BASE
    HEADLOSS = "headloss", float, FieldGroup.BASE
    VELOCITY = "velocity", float, FieldGroup.BASE

    QUALITY = "quality", float, FieldGroup.WATER_QUALITY_ANALYSIS
    REACTION_RATE = "reaction_rate", float, FieldGroup.WATER_QUALITY_ANALYSIS

    @property
    def friendly_name(self):
        if self is ResultField.DEMAND:
            return tr("Demand")
        if self is ResultField.HEAD:
            return tr("Head")
        if self is ResultField.PRESSURE:
            return tr("Pressure")
        if self is ResultField.FLOWRATE:
            return tr("Flowrate")
        if self is ResultField.HEADLOSS:
            return tr("Headloss")
        if self is ResultField.VELOCITY:
            return tr("Velocity")
        if self is ResultField.QUALITY:
            return tr("Quality")
        if self is ResultField.REACTION_RATE:
            return tr("Reaction Rate")
        raise ValueError
