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

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterCrs,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFile,
)

from wntrqgis.utilswithoutwntr import WqAnalysisType, WqFlowUnit, WqInField, WqInLayer, WqProjectVar, WqUtil
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

    def processAlgorithm(self, parameters, context, feedback):  # noqa N802
        if feedback is None:
            feedback = QgsProcessingFeedback()

        # PREPARE IMPORTS
        # imports are here as they are slow and only needed when processing the model.
        self._check_and_unpack_dependencies(feedback)
        try:
            import wntr

            from wntrqgis.utilswithwntr import WqWntrUtils
        except ImportError as e:
            raise QgsProcessingException(e) from e

        feedback.pushDebugInfo("WNTR version: " + wntr.__version__)

        if feedback.isCanceled():
            return {}
        self._update_progress(feedback, ProgStatus.LOADING_INP_FILE)

        source = self.parameterAsFile(parameters, self.INPUT, context)
        crs = self.parameterAsCrs(parameters, self.CRS, context)

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        try:
            wn = wntr.network.read_inpfile(source)
            wn_gis = wntr.network.to_gis(wn)
            gdfs = {lyr: getattr(wn_gis, lyr.wntr_attr) for lyr in WqInLayer}
        except ModuleNotFoundError as e:
            raise QgsProcessingException("WNTR dependencies not installed: " + str(e)) from e
        except Exception as e:
            raise QgsProcessingException("Error loading model: " + str(e)) from e
        if feedback.isCanceled():
            return {}
        self._describe_model(feedback, wn)

        self._update_progress(feedback, ProgStatus.CREATING_OUTPUTS)

        # Hadle which units to ouptut in
        unit_enum_int = self.parameterAsEnum(parameters, self.UNITS, context)
        if unit_enum_int is not None:
            if len(WqFlowUnit) <= unit_enum_int:
                raise QgsProcessingException(self.tr("Could not find flow unit specified"))
            wq_flow_unit = list(WqFlowUnit)[unit_enum_int]
        else:
            wq_flow_unit = WqFlowUnit[wn.options.hydraulic.inpfile_units]
        feedback.pushInfo("Will output with the following units: " + str(wq_flow_unit))
        flow_units = wntr.epanet.util.FlowUnits[wq_flow_unit.name]
        WqUtil.set_project_var(WqProjectVar.FLOW_UNITS, wq_flow_unit.name)

        WqWntrUtils.pattern_curves_to_dfs(gdfs, wn, flow_units)

        analysis_types = WqAnalysisType.BASE
        for lyr in WqInLayer:
            cols = list(gdfs[lyr].loc[:, ~gdfs[lyr].isna().all()].columns)
            for col in cols:
                try:
                    analysis_types = analysis_types | WqInField(col).analysis_type
                except ValueError:
                    continue

        extra_analysis_type_names = [
            atype.name for atype in WqAnalysisType if atype is not WqAnalysisType.BASE and atype in analysis_types
        ]
        if len(extra_analysis_type_names):
            feedback.pushInfo("Will include columns for analysis types: " + ", ".join(extra_analysis_type_names))

        WqWntrUtils.convert_dfs_from_si(gdfs, flow_units, wn.options.hydraulic.headloss == "D-W")

        outputs = {}
        for layer in WqInLayer:
            fields = layer.qgs_fields(analysis_types)

            (sink, outputs[layer.name]) = self.parameterAsSink(
                parameters, layer.name, context, fields, layer.qgs_wkb_type, crs
            )

            if not gdfs[layer].shape[0]:
                continue

            WqWntrUtils.input_gdf_to_sink(gdfs[layer], fields, sink)

        self._update_progress(feedback, ProgStatus.FINISHED_PROCESSING)

        # controls = []
        # for k, c in wn.controls.items():
        #    cc = c.to_dict()
        #    if "name" in cc and not cc["name"]:
        #        cc["name"] = k
        #    controls.append(cc)

        WqUtil.set_project_var(WqProjectVar.OPTIONS, wn.options.to_dict())

        for layername, lyr_id in outputs.items():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create(layername)
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])

        return outputs
