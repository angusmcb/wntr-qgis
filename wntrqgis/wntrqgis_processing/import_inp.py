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

from wntrqgis.utilswithoutwntr import WqAnalysisType, WqFlowUnit, WqInLayer, WqProjectVar
from wntrqgis.wntrqgis_processing.common import LayerPostProcessor, ProgStatus, WntrQgisProcessingBase


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
            This will also import all of the options from the .inp file.
            All values will be in SI units (metres, kg, seconds, m3/s, etc).
            """)

    def initAlgorithm(self, config=None):  # noqa N802
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT,
                self.tr("Epanet Input File (.inp)"),
                behavior=QgsProcessingParameterFile.File,
                extension="inp",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterCrs(self.CRS, self.tr("Coordinate Reference System (CRS)"), "ProjectCrs")
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.UNITS,
                self.tr("Units to to convert to (leave blank to use .inp file units)"),
                options=list(WqFlowUnit),
                allowMultiple=False,
                usesStaticStrings=False,
                defaultValue=None,
                optional=True,
            )
        )

        for layer in WqInLayer:
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

        # PREPARE IMPORTS
        # imports are here as they are slow and only needed when processing the model.
        self._check_and_unpack_dependencies()
        try:
            import wntr

            from wntrqgis.utilswithwntr import WqNetworkModel
        except ImportError as e:
            raise QgsProcessingException(e) from e

        feedback.pushDebugInfo("WNTR version: " + wntr.__version__)

        if feedback.isCanceled():
            return {}
        self._update_progress(ProgStatus.LOADING_INP_FILE)

        source = self.parameterAsFile(parameters, self.INPUT, context)
        crs = self.parameterAsCrs(parameters, self.CRS, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        try:
            wn = wntr.network.read_inpfile(source)

        except ModuleNotFoundError as e:
            raise QgsProcessingException("WNTR dependencies not installed: " + str(e)) from e
        except Exception as e:
            raise QgsProcessingException("Error loading model: " + str(e)) from e
        if feedback.isCanceled():
            return {}
        self._describe_model(wn)

        # Hadle which units to ouptut in
        unit_enum_int = self.parameterAsEnum(parameters, self.UNITS, context)
        if unit_enum_int is not None:
            try:
                wq_flow_unit = list(WqFlowUnit)[unit_enum_int]
            except ValueError as e:
                msg = self.tr("Could not find flow unit specified")
                raise QgsProcessingException(msg) from e
        else:
            wq_flow_unit = WqFlowUnit[wn.options.hydraulic.inpfile_units]
        feedback.pushInfo("Will output with the following units: " + str(wq_flow_unit))
        flow_units = wntr.epanet.util.FlowUnits[wq_flow_unit.name]
        WqProjectVar.FLOW_UNITS.set(wq_flow_unit.name)

        self._update_progress(ProgStatus.CREATING_OUTPUTS)

        network_model = WqNetworkModel(flow_units, wn.options.hydraulic.headloss == "D-W")

        network_model.from_wntr(wn)

        extra_analysis_type_names = [
            atype.name
            for atype in WqAnalysisType
            if atype is not WqAnalysisType.BASE and atype in network_model.analysis_types and atype.name is not None
        ]
        if len(extra_analysis_type_names):
            feedback.pushInfo("Will include columns for analysis types: " + ", ".join(extra_analysis_type_names))

        outputs = {}
        sinks = {}
        for layer in WqInLayer:
            fields = layer.qgs_fields(network_model.analysis_types)
            (sink, outputs[layer.name]) = self.parameterAsSink(
                parameters, layer.name, context, fields, layer.qgs_wkb_type, crs
            )
            sinks[layer] = (sink, fields)

        network_model.write_to_sinks(sinks)

        self._update_progress(ProgStatus.FINISHED_PROCESSING)

        WqProjectVar.OPTIONS.set(wn.options.to_dict())

        filename = Path(source).stem

        for layername, lyr_id in outputs.items():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(
                    layername, self.tr(f"Model Layers ({filename})")
                )
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])

        return outputs
