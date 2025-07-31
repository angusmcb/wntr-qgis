from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from wntrqgis.elements import Field, FlowUnit, HeadlossFormula, ModelLayer, Parameter, ResultLayer

if TYPE_CHECKING:
    import pandas as pd
    from numpy.typing import ArrayLike


class MassUnits(enum.Enum):
    r"""Mass units used by EPANET, plus SI conversion factor.

    Mass units are defined in the EPANET INP file when the QUALITY option is
    set to a chemical. This is parsed to obtain the mass part of the concentration units,
    and is used to set this enumerated type.

    .. rubric:: Enum Members

    ============  ============================================
    :attr:`~mg`   miligrams; EPANET as "mg/L" or "mg/min"
    :attr:`~ug`   micrograms; EPANET as "ug/L" or "ug/min"
    :attr:`~g`    grams
    :attr:`~kg`   kilograms; WNTR standard
    ============  ============================================

    .. rubric:: Enum Member Attributes

    .. autosummary::
        factor

    """

    mg = (1, 0.000001)
    ug = (2, 0.000000001)
    g = (3, 0.001)
    kg = (4, 1.0)

    @property
    def factor(self):
        """float : The scaling factor to convert to kg."""
        value = super().value
        return value[1]


class Converter:
    """Manages conversion to and from SI units

    Args:
        flow_units: The set of units which will be converted to/from (or SI units for no conversion)
        headloss_formula: Used to determine how to handle conversion of the roughness coefficient
    """

    def __init__(
        self,
        flow_units: FlowUnit,
        headloss_formula: HeadlossFormula,
    ):
        self.flow_units = flow_units
        self.headloss_formula = headloss_formula
        self.mass_units = MassUnits.mg
        self.reaction_order = 0

    def to_si(
        self,
        value: float | ArrayLike | pd.api.extensions.ExtensionArray | pd.Series | pd.DataFrame,
        field: Field | Parameter,
        layer: ModelLayer | ResultLayer | None = None,
    ) -> float | ArrayLike | pd.api.extensions.ExtensionArray | pd.Series | pd.DataFrame:
        conversion_param = self._get_conversion_param(field, layer)

        if not conversion_param:
            return value

        return value * self._factor(conversion_param)

    def from_si(
        self,
        value: float | ArrayLike | pd.api.extensions.ExtensionArray | pd.Series | pd.DataFrame,
        field: Field | Parameter,
        layer: ModelLayer | ResultLayer | None = None,
    ) -> float | ArrayLike | pd.api.extensions.ExtensionArray | pd.Series | pd.DataFrame:
        conversion_param = self._get_conversion_param(field, layer)

        if not conversion_param:
            return value

        return value / self._factor(conversion_param)

    def _get_conversion_param(
        self, field: Field | Parameter, layer: ModelLayer | ResultLayer | None = None
    ) -> Parameter | None:
        if isinstance(field, Parameter):
            return field

        if field.python_type is not float:
            return None

        if field is Field.ELEVATION:
            return Parameter.Elevation
        if field is Field.BASE_DEMAND or field is Field.DEMAND:
            return Parameter.Demand
        if field is Field.EMITTER_COEFFICIENT:
            return Parameter.EmitterCoeff
        if field in [Field.INITIAL_QUALITY, Field.QUALITY]:
            return Parameter.Quality
        if field in [Field.MINIMUM_PRESSURE, Field.REQUIRED_PRESSURE, Field.PRESSURE]:
            return Parameter.Pressure
        if field in [
            Field.INIT_LEVEL,
            Field.MIN_LEVEL,
            Field.MAX_LEVEL,
            Field.BASE_HEAD,
            Field.HEAD,
        ]:
            return Parameter.HydraulicHead
        if field is Field.DIAMETER and layer is ModelLayer.TANKS:
            return Parameter.TankDiameter
        if field is Field.DIAMETER:
            return Parameter.PipeDiameter
        if field is Field.MIN_VOL:
            return Parameter.Volume
        if field is Field.BULK_COEFF:
            return Parameter.BulkReactionCoeff
        if field is Field.LENGTH:
            return Parameter.Length
        if field is Field.ROUGHNESS:
            return Parameter.RoughnessCoeff
        if field is Field.WALL_COEFF:
            return Parameter.WallReactionCoeff
        if field is Field.POWER:
            return Parameter.Power
        if field is Field.FLOWRATE:
            return Parameter.Flow
        if field is Field.HEADLOSS:
            if layer is ModelLayer.PIPES:
                return Parameter.Headloss
            return Parameter.HydraulicHead
        if field is Field.VELOCITY:
            return Parameter.Velocity

        if field in [
            Field.MINOR_LOSS,
            Field.BASE_SPEED,
            Field.INITIAL_SETTING,
            Field.MIXING_FRACTION,
            Field.PRESSURE_EXPONENT,
            Field.ENERGY_PRICE,
            Field.REACTION_RATE,
        ]:
            return None

        raise ValueError(field)  # pragma: no cover

    def _factor(
        self,
        parameter,
    ) -> float:
        """Convert from EPANET units groups to SI units.

        If converting roughness, specify if the Darcy-Weisbach equation is
        used using the darcy_weisbach parameter. Otherwise, that parameter
        can be safely ignored/omitted for any other conversion.

        Parameters
        ----------
        flow_units : FlowUnits
            The flow units to use in the conversion
        data : array-like
            The EPANET-units data to be converted (scalar, array or dictionary)
        darcy_weisbach : bool, optional
            Set to ``True`` if converting roughness coefficients for use with Darcy-Weisbach
            formula.

        Returns
        -------
        float
            The data values converted to SI standard units.

        """

        traditional = self.flow_units in [FlowUnit.CFS, FlowUnit.GPM, FlowUnit.MGD, FlowUnit.IMGD, FlowUnit.AFD]

        if parameter in [Parameter.Demand, Parameter.Flow, Parameter.EmitterCoeff]:
            return self._flow_unit_factor()

        if parameter is Parameter.EmitterCoeff:
            if traditional:
                # flowunit/sqrt(psi) to flowunit/sqrt(m), i.e.,
                # flowunit/sqrt(psi) * sqrt(psi/ft / m/ft ) = flowunit/sqrt(m)
                return self._flow_unit_factor() * (0.4333 / 0.3048) ** 0.5
            else:
                return self._flow_unit_factor()

        elif parameter is Parameter.PipeDiameter:
            if traditional:
                return 0.0254  # in to m
            else:
                return 0.001  # mm to m

        elif parameter is Parameter.RoughnessCoeff and self.headloss_formula is HeadlossFormula.DARCY_WEISBACH:
            if traditional:
                return 0.001 * 0.3048  # 1e-3 ft to m
            else:
                return 0.001  # mm to m

        elif parameter in [Parameter.TankDiameter, Parameter.Elevation, Parameter.HydraulicHead, Parameter.Length]:
            if traditional:
                return 0.3048  # ft to m

        elif parameter is Parameter.Headloss:
            return 0.001  # m/1000m or ft/1000ft to unitless

        elif parameter is Parameter.Velocity:
            if traditional:
                return 0.3048  # ft/s to m/s

        elif parameter is Parameter.Energy:
            return 3600000.0  # kW*hr to J

        elif parameter is Parameter.Power:
            if traditional:
                return 745.699872  # hp to W (Nm/s)
            else:
                return 1000.0  # kW to W (Nm/s)

        elif parameter is Parameter.Pressure:
            if traditional:
                # psi to m, i.e., psi * (m/ft / psi/ft) = m
                return 0.3048 / 0.4333

        elif parameter is Parameter.Volume:
            if traditional:
                return 0.3048**3  # ft3 to m3

        elif parameter in [Parameter.Concentration, Parameter.Quality, Parameter.LinkQuality]:
            return self.mass_units.factor / 0.001  # MASS /L to kg/m3
        elif parameter is Parameter.ReactionRate:
            return (self.mass_units.factor / 0.001) / (24 * 3600)  # 1/day to 1/s

        elif parameter is Parameter.SourceMassInject:
            return self.mass_units.factor / 60.0  # MASS /min to kg/s

        elif parameter is Parameter.BulkReactionCoeff and self.reaction_order == 1:
            return 1 / 86400.0  # per day to per second

        elif parameter is Parameter.WallReactionCoeff and self.reaction_order == 0:
            if traditional:
                return self.mass_units.factor * 0.092903 / 86400.0  # M/ft2/d to SI
            else:
                return self.mass_units.factor / 86400.0  # M/m2/day to M/m2/s

        elif parameter is Parameter.WallReactionCoeff and self.reaction_order == 1:
            if traditional:
                return 0.3048 / 86400.0  # ft/d to m/s
            else:
                return 1.0 / 86400.0  # m/day to m/s

        elif parameter is Parameter.SourceMassInject:
            return self.mass_units.factor / 60.0  # per min to per second

        elif parameter is Parameter.WaterAge:
            return 3600.0  # hr to s

        return 1.0

    def _flow_unit_factor(self) -> float:
        flow_units = self.flow_units
        if flow_units is FlowUnit.CFS:
            factor = 0.0283168466
        elif flow_units is FlowUnit.GPM:
            factor = 0.003785411784 / 60.0
        elif flow_units is FlowUnit.MGD:
            factor = 1e6 * 0.003785411784 / 86400.0
        elif flow_units is FlowUnit.IMGD:
            factor = 1e6 * 0.00454609 / 86400.0
        elif flow_units is FlowUnit.AFD:
            factor = 1233.48184 / 86400.0
        elif flow_units is FlowUnit.LPS:
            factor = 0.001
        elif flow_units is FlowUnit.LPM:
            factor = 0.001 / 60.0
        elif flow_units is FlowUnit.MLD:
            factor = 1e6 * 0.001 / 86400.0
        elif flow_units is FlowUnit.CMH:
            factor = 1.0 / 3600.0
        elif flow_units is FlowUnit.CMD:
            factor = 1.0 / 86400.0
        else:
            raise ValueError(f"Unknown flow unit: {flow_units}")  # noqa: EM102, TRY003 # pragma: no cover

        return factor
