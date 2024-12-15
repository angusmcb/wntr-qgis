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

from pathlib import Path
from typing import Any

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterCrs,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFile,
)

from wntrqgis.network_parts import (
    FieldGroup,
    FlowUnit,
    HeadlossFormula,
    ModelLayer,
)
from wntrqgis.resource_manager import WqIcon
from wntrqgis.settings import WqProjectSetting, WqProjectSettings
from wntrqgis.wntrqgis_processing.common import ProgStatus, WntrQgisProcessingBase


class ImportInp(QgsProcessingAlgorithm, WntrQgisProcessingBase):
    INPUT = "INPUT"
    CRS = "CRS"
    UNITS = "UNITS"

    def createInstance(self):  # noqa N802
        return ImportInp()

    def name(self):
        return "importinp"

    def displayName(self):  # noqa N802
        return self.tr("Import from Epanet INP file")

    def shortHelpString(self):  # noqa N802
        return self.tr("""
            Import all junctions, tanks, reservoirs, pipes, pumps and valves from an EPANET inp file.
            This will also save selected options from the .inp file.
            All units will be converted into the unit set selected. If not selected, it will default \
            to the unit set in the .inp file.
            """)

    def icon(self):
        return WqIcon.OPEN.q_icon

    def initAlgorithm(self, config=None):  # noqa N802
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT,
                self.tr("Epanet Input File (.inp)"),
                behavior=QgsProcessingParameterFile.File,
                extension="inp",
            )
        )
        self.addParameter(
            QgsProcessingParameterCrs(self.CRS, self.tr("Coordinate Reference System (CRS)"), "ProjectCrs")
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.UNITS,
                self.tr("Units to to convert to (leave blank to use .inp file units)"),
                options=[fu.value for fu in FlowUnit],
                optional=True,
            )
        )

        for layer in ModelLayer:
            self.addParameter(QgsProcessingParameterFeatureSink(layer.name, self.tr(layer.friendly_name)))

    def preprocessParameters(self, parameters):  # noqa N802
        if not Path(parameters[self.INPUT]).is_file():
            example_file = Path(__file__).parent.parent / "resources" / "examples" / parameters[self.INPUT]
            if example_file.is_file():
                parameters[self.INPUT] = str(example_file)

        return parameters

    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict:
        WntrQgisProcessingBase.processAlgorithm(self, parameters, context, feedback)

        # imports are here as they are slow, will break if wntr isn't installed, and only needed in processalgorithm()
        self._ensure_wntr()

        import wntr

        from wntrqgis.wntr_interface import NetworkFromWntr, UnitConversion

        self._update_progress(ProgStatus.LOADING_INP_FILE)

        input_file = self.parameterAsFile(parameters, self.INPUT, context)

        try:
            wn = wntr.network.read_inpfile(input_file)
        except FileNotFoundError as e:
            msg = f".inp file does not exist ({input_file})"
            raise QgsProcessingException(msg) from e
        self._describe_model(wn)

        # Hadle which units to ouptut in
        if parameters.get(self.UNITS) is not None:
            unit_enum_int = self.parameterAsEnum(parameters, self.UNITS, context)
            try:
                wq_flow_unit = list(FlowUnit)[unit_enum_int]
            except ValueError as e:
                msg = self.tr("Could not find flow unit specified")
                raise QgsProcessingException(msg) from e
        else:
            wq_flow_unit = FlowUnit[wn.options.hydraulic.inpfile_units]
        feedback.pushInfo("Will output with the following units: " + str(wq_flow_unit.value))

        wq_headloss_formula = HeadlossFormula(wn.options.hydraulic.headloss)

        unit_conversion = UnitConversion(wq_flow_unit, wq_headloss_formula)

        project_settings = WqProjectSettings(context.project())
        project_settings.set(WqProjectSetting.FLOW_UNITS, wq_flow_unit)
        project_settings.set(WqProjectSetting.HEADLOSS_FORMULA, wq_headloss_formula)
        project_settings.set(WqProjectSetting.SIMULATION_DURATION, wn.options.time.duration / 3600)

        self._update_progress(ProgStatus.CREATING_OUTPUTS)

        network_model = NetworkFromWntr(wn, unit_conversion)

        # this is just to give a little user output
        extra_analysis_type_names = [
            str(atype.name)
            for atype in [FieldGroup.ENERGY, FieldGroup.WATER_QUALITY_ANALYSIS, FieldGroup.PRESSURE_DEPENDENT_DEMAND]
            if network_model.field_groups is not None and atype in network_model.field_groups
        ]
        if len(extra_analysis_type_names):
            feedback.pushInfo("Will include columns for analysis types: " + ", ".join(extra_analysis_type_names))

        crs = self.parameterAsCrs(parameters, self.CRS, context)

        outputs: dict[str, str] = {}

        for layer in ModelLayer:
            fields = layer.qgs_fields(network_model.field_groups)
            (sink, outputs[layer]) = self.parameterAsSink(
                parameters, layer.name, context, fields, layer.qgs_wkb_type, crs
            )
            network_model.write_to_sink(layer, fields, sink)

        self._update_progress(ProgStatus.FINISHED_PROCESSING)

        filename = Path(input_file).stem

        self._setup_postprocessing(outputs, f"Model Layers ({filename})", False)

        return outputs
