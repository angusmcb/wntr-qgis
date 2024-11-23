"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from __future__ import annotations

from typing import Any, ClassVar  # noqa F401

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterVectorLayer,
    QgsProject,
)

from wntrqgis.network_parts import (
    WqFlowUnit,
    WqHeadlossFormula,
    WqModelLayer,
    WqProjectSetting,
    WqProjectSettings,
)
from wntrqgis.wntrqgis_processing.common import WntrQgisProcessingBase


class SettingsAlgorithm(QgsProcessingAlgorithm, WntrQgisProcessingBase):
    UNITS = "UNITS"
    DURATION = "DURATION"
    HEADLOSS_FORMULA = "HEADLOSS_FORMULA"

    def createInstance(self):  # noqa N802
        return SettingsAlgorithm()

    def name(self):
        return "settings"

    def displayName(self):  # noqa N802
        return self.tr("Settings")

    def shortHelpString(self):  # noqa N802
        return self.tr("""
            The settings you configure here will be used when using the 'run' button.
            """)

    def flags(self):
        return self.FlagHideFromToolbox

    def initAlgorithm(self, config=None):  # noqa N802
        project_settings = WqProjectSettings(QgsProject.instance())

        default_layers = project_settings.get(WqProjectSetting.MODEL_LAYERS, {})
        for lyr in WqModelLayer:
            param = QgsProcessingParameterVectorLayer(
                lyr.name,
                self.tr(lyr.friendly_name),
                types=lyr.acceptable_processing_vectors,
                optional=True,  # lyr is not WqModelLayer.JUNCTIONS,
            )
            savedlyr = default_layers.get(lyr.name)
            if savedlyr and param.checkValueIsAcceptable(savedlyr) and QgsProject.instance().mapLayer(savedlyr):
                param.setGuiDefaultValueOverride(savedlyr)

            self.addParameter(param)

        param = QgsProcessingParameterEnum(
            self.UNITS,
            self.tr("Units"),
            options=[fu.value for fu in WqFlowUnit],
            allowMultiple=False,
            usesStaticStrings=False,
            optional=True,
        )
        default_flow_units = project_settings.get(WqProjectSetting.FLOW_UNITS)
        param.setGuiDefaultValueOverride(list(WqFlowUnit).index(default_flow_units) if default_flow_units else None)
        self.addParameter(param)

        param = QgsProcessingParameterEnum(
            self.HEADLOSS_FORMULA,
            self.tr("Headloss Formula"),
            options=[formula.friendly_name for formula in WqHeadlossFormula],
            allowMultiple=False,
            usesStaticStrings=False,
            optional=True,
        )
        default_hl_formula = project_settings.get(WqProjectSetting.HEADLOSS_FORMULA)
        param.setGuiDefaultValueOverride(
            list(WqHeadlossFormula).index(default_hl_formula) if default_hl_formula else None
        )
        self.addParameter(param)

        param = QgsProcessingParameterNumber(
            self.DURATION, self.tr("Simulation duration in hours (or 0 for single period)"), minValue=0
        )
        param.setGuiDefaultValueOverride(project_settings.get(WqProjectSetting.SIMULATION_DURATION, 0))
        self.addParameter(param)

    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict:
        WntrQgisProcessingBase.processAlgorithm(self, parameters, context, feedback)

        project_settings = WqProjectSettings(context.project())

        flow_unit_index = self.parameterAsEnum(parameters, self.UNITS, context)
        wq_flow_unit = list(WqFlowUnit)[flow_unit_index]
        project_settings.set(WqProjectSetting.FLOW_UNITS, wq_flow_unit)

        headloss_formula_index = self.parameterAsEnum(parameters, self.HEADLOSS_FORMULA, context)
        headloss_formula = list(WqHeadlossFormula)[headloss_formula_index]
        project_settings.set(WqProjectSetting.HEADLOSS_FORMULA, headloss_formula)

        duration = self.parameterAsDouble(parameters, self.DURATION, context)
        project_settings.set(WqProjectSetting.SIMULATION_DURATION, duration)

        sources = {
            lyr: input_layer.id()
            for lyr in WqModelLayer
            if (input_layer := self.parameterAsVectorLayer(parameters, lyr.name, context))
        }

        project_settings.set(WqProjectSetting.MODEL_LAYERS, sources)
        return {}
