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

import warnings
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

from wntrqgis.elements import (
    # FieldGroup,
    FlowUnit,
    HeadlossFormula,
    ModelLayer,
)
from wntrqgis.i18n import tr
from wntrqgis.interface import Writer
from wntrqgis.resource_manager import WqIcon
from wntrqgis.settings import ProjectSettings, SettingKey
from wntrqgis.wntrqgis_processing.common import Progression, WntrQgisProcessingBase


class ImportInp(QgsProcessingAlgorithm, WntrQgisProcessingBase):
    INPUT = "INPUT"
    CRS = "CRS"
    UNITS = "UNITS"

    def createInstance(self):  # noqa N802
        return ImportInp()

    def name(self):
        return "importinp"

    def displayName(self):  # noqa N802
        return tr("Import from Epanet INP file")

    def shortHelpString(self):  # noqa N802
        return tr("""
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
                tr("Epanet Input File (.inp)"),
                behavior=QgsProcessingParameterFile.File,
                extension="inp",
            )
        )

        param = QgsProcessingParameterCrs(self.CRS, tr("Coordinate Reference System (CRS)"))
        param.setGuiDefaultValueOverride("ProjectCrs")
        self.addParameter(param)

        self.addParameter(
            QgsProcessingParameterEnum(
                self.UNITS,
                tr("Units to to convert to (leave blank to use .inp file units)"),
                options=[fu.friendly_name for fu in FlowUnit],
                optional=True,
            )
        )

        for layer in ModelLayer:
            self.addParameter(QgsProcessingParameterFeatureSink(layer.name, layer.friendly_name))

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

        self._update_progress(Progression.LOADING_INP_FILE)

        input_file = self.parameterAsFile(parameters, self.INPUT, context)

        try:
            wn: wntr.network.WaterNetworkModel = wntr.network.read_inpfile(input_file)
        except FileNotFoundError as e:
            msg = f".inp file does not exist ({input_file})"
            raise QgsProcessingException(msg) from e
        except wntr.epanet.exceptions.EpanetException as e:
            msg = f"error reading .inp file: {e}"
            raise QgsProcessingException(msg) from e

        self._describe_model(wn)

        if parameters.get(self.UNITS) is not None:
            unit_enum_int = self.parameterAsEnum(parameters, self.UNITS, context)
            flow_unit = list(FlowUnit)[unit_enum_int]
        else:
            flow_unit = FlowUnit[wn.options.hydraulic.inpfile_units]
        feedback.pushInfo(
            tr("Will output with the following units: {flow_unit}").format(flow_unit=flow_unit.friendly_name)
        )

        headloss_formula = HeadlossFormula(wn.options.hydraulic.headloss)

        project_settings = ProjectSettings(context.project())
        project_settings.set(SettingKey.FLOW_UNITS, flow_unit)
        project_settings.set(SettingKey.HEADLOSS_FORMULA, headloss_formula)
        project_settings.set(SettingKey.SIMULATION_DURATION, wn.options.time.duration / 3600)

        self._update_progress(Progression.CREATING_OUTPUTS)

        network_writer = Writer(wn, units=flow_unit.name)  # TODO: FlowUnits should be string that doesn't need 'name'

        # this is just to give a little user output
        # extra_analysis_type_names = [
        #     str(atype.name)
        #     for atype in [FieldGroup.ENERGY, FieldGroup.WATER_QUALITY_ANALYSIS, FieldGroup.PRESSURE_DEPENDENT_DEMAND]
        #     if network_model.field_groups is not None and atype in network_model.field_groups
        # ]
        # if len(extra_analysis_type_names):
        #     feedback.pushInfo("Will include columns for analysis types: " + ", ".join(extra_analysis_type_names))

        crs = self.parameterAsCrs(parameters, self.CRS, context)

        # for shapefile writing
        warnings.filterwarnings("ignore", "Field", RuntimeWarning)
        warnings.filterwarnings("ignore", "Normalized/laundered field name:", RuntimeWarning)

        outputs: dict[str, str] = {}
        layers: dict[ModelLayer, str] = {}
        for layer in ModelLayer:
            fields = network_writer.get_qgsfields(layer)
            (sink, outputs[layer.name]) = self.parameterAsSink(
                parameters, layer.name, context, fields, layer.qgs_wkb_type, crs
            )
            layers[layer] = outputs[layer.name]
            network_writer.write(layer, sink)

        self._update_progress(Progression.FINISHED_PROCESSING)

        filename = Path(input_file).stem

        self._setup_postprocessing(layers, tr("Model Layers ({filename})").format(filename=filename), False)

        return outputs
