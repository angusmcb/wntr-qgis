from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.core import (
    QgsExpressionContextUtils,
    QgsField,
    QgsFields,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication, QVariant


class EmptyLayers(QgsProcessingAlgorithm):
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.

    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    CRS = "CRS"
    PRESSUREDEPENDENT = "PRESSUREDEPENEDENT"
    QUALITY = "QUALITY"
    ENERGY = "ENERGY"
    JUNCTIONS = "JUNCTIONS"
    TANKS = "TANKS"
    RESERVOIRS = "RESERVOIRS"
    PIPES = "PIPES"
    PUMPS = "PUMPS"
    VALVES = "VALVES"

    post_processors = dict()

    def __init__(self) -> None:
        super().__init__()

        self._name = "emptymodel"
        self._display_name = "Create Empty Layers"
        self._group_id = ""
        self._group = ""
        self._short_help_string = ""

    def tr(self, string) -> str:
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):  # noqa N802
        return EmptyLayers()

    def name(self) -> str:
        return self._name

    def displayName(self) -> str:  # noqa N802
        return self.tr(self._display_name)

    def groupId(self) -> str:  # noqa N802
        return self._group_id

    def group(self) -> str:
        return self.tr(self._group)

    def shortHelpString(self) -> str:  # noqa N802
        return self.tr(self._short_help_string)

    def initAlgorithm(self, config=None):  # noqa N802
        self.addParameter(QgsProcessingParameterCrs(self.CRS, "CRS", 'ProjectCrs'))

        param = QgsProcessingParameterBoolean(self.QUALITY, 'Create Fields for Water Quality Analysis', optional=True, defaultValue=False)
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterBoolean(self.PRESSUREDEPENDENT, 'Create Fields for Pressure-Dependent Demand Analysis', optional=True, defaultValue=False)
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterBoolean(self.ENERGY, 'Create Fields for Energy Analysis', optional=True, defaultValue=False)
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        self.addParameter(QgsProcessingParameterFeatureSink(self.JUNCTIONS, self.tr("Junctions")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.TANKS, self.tr("Tanks")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.RESERVOIRS, self.tr("Reservoirs")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.PIPES, self.tr("Pipes")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.PUMPS, self.tr("Pumps")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.VALVES, self.tr("Valves")))

    def processAlgorithm(  # noqa N802
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict:
        """
        Here is where the processing itself takes place.
        """

        # Initialize feedback if it is None
        if feedback is None:
            feedback = QgsProcessingFeedback()

        # derived from running wntr.network.io.valid_gis_names(True)
        fieldnames = {
            "junctions": [
                "name",
                "elevation",
                "base_demand",
                "emitter_coefficient",
                "initial_quality",
                "minimum_pressure",
                "required_pressure",
                "pressure_exponent",

            ],
            "tanks": [
                "name",
                "elevation",
                "init_level",
                "min_level",
                "max_level",
                "diameter",
                "min_vol","vol_curve_name",
                "overflow",
                "initial_quality",
                "mixing_fraction",
                "mixing_model",
                "bulk_coeff",

            ],
            "reservoirs": ["name", "base_head", "head_pattern_name", "initial_quality"],
            "pipes": [
                "name",
                "start_node_name",
                "end_node_name",
                "length",
                "diameter",
                "roughness",
                "minor_loss",
                "initial_status",
                "check_valve",
                "bulk_coeff",
                "wall_coeff",

            ],
            "pumps": [
                "name",
                "start_node_name",
                "end_node_name",
                "pump_type",
                "pump_curve_name",
                "powerbase_speed",
                "speed_pattern_name",
                "initial_status",
                "initial_setting",
                "efficiency",
                "energy_pattern",
                "energy_price",

            ],
            "valves": [
                "name",
                "start_node_name",
                "end_node_name",
                "diameter",
                "valve_type",
                "minor_loss",
                "initial_setting",
                "initial_status",

            ],
        }

        fieldtypes ={
            'BASE': {
                "name": QVariant.String,
                "node_type": QVariant.String,
                "link_type": QVariant.String,
                "elevation": QVariant.Double,
                "base_demand": QVariant.Double,
                "emitter_coefficient": QVariant.Double,
                "init_level": QVariant.Double,
                "min_level": QVariant.Double,
                "max_level": QVariant.Double,
                "diameter": QVariant.Double,
                "min_vol":QVariant.Double,
                "vol_curve_name": QVariant.String,
                "overflow": QVariant.Bool,
                "base_head": QVariant.Double,
                "head_pattern_name": QVariant.String,
                "start_node_name": QVariant.String,
                "end_node_name": QVariant.String,
                "length": QVariant.Double,
                "roughness": QVariant.Double,
                "minor_loss": QVariant.Double,
                "initial_status": QVariant.String,
                "check_valve": QVariant.Bool,
                "pump_type": QVariant.String,
                "pump_curve_name": QVariant.String,
                "powerbase_speed": QVariant.Double,
                "speed_pattern_name": QVariant.String,
                "initial_setting": QVariant.String,
                "valve_type": QVariant.String,
        },
        self.QUALITY:
        {
            "initial_quality": QVariant.Double,
            "mixing_fraction": QVariant.Double,
            "mixing_model": QVariant.String,
            "bulk_coeff": QVariant.Double,
            "wall_coeff": QVariant.Double,
        },
        self.PRESSUREDEPENDENT:
         {
            "minimum_pressure": QVariant.Double,
            "required_pressure": QVariant.Double,
            "pressure_exponent": QVariant.Double,
        },
        self.ENERGY: {
            "efficiency": QVariant.Double,
            "energy_pattern": QVariant.String,
            "energy_price": QVariant.Double,
        }}

        fieldstouse = fieldtypes['BASE']
        for i in [self.QUALITY,self.PRESSUREDEPENDENT,self.ENERGY]:
            if self.parameterAsBoolean(parameters, i, context):
                fieldstouse.update(fieldtypes[i])

        outputs = {
            "junctions": {"parameter": self.JUNCTIONS, "type": QgsWkbTypes.Point},
            "tanks": {"parameter": self.TANKS, "type": QgsWkbTypes.Point},
            "reservoirs": {"parameter": self.RESERVOIRS, "type": QgsWkbTypes.Point},
            "pipes": {"parameter": self.PIPES, "type": QgsWkbTypes.LineString},
            "pumps": {"parameter": self.PUMPS, "type": QgsWkbTypes.LineString},
            "valves": {"parameter": self.VALVES, "type": QgsWkbTypes.LineString},
        }

        returnoutputs = dict()

        for i in outputs:
            fields = QgsFields()
            for j in fieldnames[i]:
                if j in fieldstouse:
                    fields.append(QgsField(j, fieldstouse[j]))

            (outputs[i]["sink"], dest_id) = self.parameterAsSink(
                parameters,
                outputs[i]["parameter"],
                context,
                fields,
                outputs[i]["type"],
                self.parameterAsCrs(parameters, self.CRS, context),
            )
            returnoutputs[outputs[i]["parameter"]] = dest_id

            if context.willLoadLayerOnCompletion(dest_id):
                self.post_processors[dest_id] = LayerPostProcessor.create(outputs[i]["parameter"])
                context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(self.post_processors[dest_id])

        """
        for lyr_id in returnoutputs.values():
            if context.willLoadLayerOnCompletion(lyr_id):
                self.post_processors[lyr_id] = LayerPostProcessor.create()
                context.layerToLoadOnCompletionDetails(lyr_id).setPostProcessor(self.post_processors[lyr_id])
        """
        return returnoutputs


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    instance = None
    layertype = None

    def postProcessLayer(self, layer, context, feedback):
        if not isinstance(layer, QgsVectorLayer):
            return
        layer.loadNamedStyle(str(Path(__file__).parent.parent / "resources" / "styles" / (self.layertype + ".qml")))
        wntr_layers = QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable("wntr_layers")
        if wntr_layers is None:
            wntr_layers = {}
        wntr_layers[self.layertype] = layer.id()
        QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(), "wntr_layers", wntr_layers)

    @staticmethod
    def create(layertype) -> LayerPostProcessor:
        LayerPostProcessor.instance = LayerPostProcessor()
        LayerPostProcessor.instance.layertype = layertype
        return LayerPostProcessor.instance
