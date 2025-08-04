from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from wntrqgis.elements import FlowUnit, HeadlossFormula, Parameter

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd
    import wntr


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
        flow_units: The set of units which will be converted to/from
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
        self.wall_reaction_order = 1

    @classmethod
    def from_wn(cls, wn: wntr.network.WaterNetworkModel) -> Converter:
        flow_units = FlowUnit[wn.options.hydraulic.inpfile_units.upper()]
        headloss_formula = HeadlossFormula(wn.options.hydraulic.headloss)
        converter = cls(flow_units, headloss_formula)
        return converter

    def to_si(
        self,
        value: float | np.ndarray[float] | pd.Series[float] | pd.DataFrame,
        parameter: Parameter,
    ) -> float | np.ndarray[float] | pd.Series[float] | pd.DataFrame:
        return value * self._factor(parameter)

    def from_si(
        self,
        value: float | np.ndarray[float] | pd.Series[float] | pd.DataFrame,
        parameter: Parameter,
    ) -> float | np.ndarray[float] | pd.Series[float] | pd.DataFrame:
        return value / self._factor(parameter)

    def _factor(
        self,
        parameter: Parameter,
    ) -> float:
        if parameter is Parameter.Flow:
            return self._flow_unit_factor()

        if parameter is Parameter.EmitterCoeff:
            if self.traditional:
                # flowunit/sqrt(psi) to flowunit/sqrt(m), i.e.,
                # flowunit/sqrt(psi) * sqrt(psi/ft / m/ft ) = flowunit/sqrt(m)
                return self._flow_unit_factor() * (0.4333 / 0.3048) ** 0.5
            else:
                return self._flow_unit_factor()

        elif parameter is Parameter.PipeDiameter:
            if self.traditional:
                return 0.0254  # in to m
            else:
                return 0.001  # mm to m

        elif parameter is Parameter.RoughnessCoeff:
            if self.headloss_formula is HeadlossFormula.DARCY_WEISBACH:
                if self.traditional:
                    return 0.001 * 0.3048  # 1e-3 ft to m
                else:
                    return 0.001  # mm to m
            else:
                return 1.0

        elif parameter in [Parameter.TankDiameter, Parameter.Elevation, Parameter.HydraulicHead, Parameter.Length]:
            if self.traditional:
                return 0.3048  # ft to m
            else:
                return 1.0

        elif parameter is Parameter.UnitHeadloss:
            return 0.001  # m/1000m or ft/1000ft to unitless

        elif parameter is Parameter.Velocity:
            if self.traditional:
                return 0.3048  # ft/s to m/s
            else:
                return 1.0

        elif parameter is Parameter.Energy:
            return 3600000.0  # kW*hr to J

        elif parameter is Parameter.Power:
            if self.traditional:
                return 745.699872  # hp to W (Nm/s)
            else:
                return 1000.0  # kW to W (Nm/s)

        elif parameter is Parameter.Pressure:
            if self.traditional:
                # psi to m, i.e., psi * (m/ft / psi/ft) = m
                return 0.3048 / 0.4333
            else:
                return 1.0

        elif parameter is Parameter.Volume:
            if self.traditional:
                return 0.3048**3  # ft3 to m3
            else:
                return 1.0

        elif parameter is Parameter.Concentration:
            return self.mass_units.factor / 0.001  # MASS /L to kg/m3

        elif parameter is Parameter.ReactionRate:
            return (self.mass_units.factor / 0.001) / (24 * 3600)  # 1/day to 1/s

        elif parameter is Parameter.SourceMassInject:
            return self.mass_units.factor / 60.0  # MASS /min to kg/s

        elif parameter is Parameter.BulkReactionCoeff:
            return 1 / 86400.0  # per day to per second

        elif parameter is Parameter.WallReactionCoeff and self.wall_reaction_order == 0:
            if self.traditional:
                return self.mass_units.factor * 0.092903 / 86400.0  # M/ft2/d to SI
            else:
                return self.mass_units.factor / 86400.0  # M/m2/day to M/m2/s

        elif parameter is Parameter.WallReactionCoeff and self.wall_reaction_order == 1:
            if self.traditional:
                return 0.3048 / 86400.0  # ft/d to m/s
            else:
                return 1.0 / 86400.0  # m/day to m/s

        elif parameter is Parameter.SourceMassInject:
            return self.mass_units.factor / 60.0  # per min to per second

        elif parameter is Parameter.WaterAge:
            return 3600.0  # hr to s

        raise ValueError(parameter)  # pragma: no cover

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
            raise ValueError(flow_units)  # pragma: no cover

        return factor

    @property
    def traditional(self):
        return self.flow_units in [FlowUnit.CFS, FlowUnit.GPM, FlowUnit.MGD, FlowUnit.IMGD, FlowUnit.AFD]
