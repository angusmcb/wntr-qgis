from qgis.core import (
    QgsField,
    QgsFields,
)
from qgis.PyQt.QtCore import QVariant


def namesByLayer(layername, extra=[]):  # noqa N802 needs refactor anyway
    typesToUse = types["BASE"]  # noqa N802
    for i in extra:
        typesToUse.update(types[i])
    return [name for name in namesPerLayer[layername] if name in typesToUse]


def getQgsFields(layername, extra=[]):  # noqa N802
    fields = QgsFields()
    flattypelist = flatTypes()
    for fieldname in namesByLayer(layername, extra):
        fields.append(QgsField(fieldname, flattypelist[fieldname]))
    return fields


def flatTypes():  # noqa N802
    output = {}
    for typelist in types.values():
        output.update(typelist)
    return output


def namesOfExtra():  # noqa N802
    output = {}
    for typecat, typelist in types.items():
        if typecat != "BASE":
            output.update({typecat: list(typelist.keys())})
    return output


# derived from running wntr.network.io.valid_gis_names(True)
namesPerLayer = {  # noqa N802
    "junctions": [
        "name",
        "elevation",
        "base_demand",
        "demand_pattern",
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
        "min_vol",
        "vol_curve",
        "overflow",
        "initial_quality",
        "mixing_fraction",
        "mixing_model",
        "bulk_coeff",
    ],
    "reservoirs": ["name", "base_head", "head_pattern", "initial_quality"],
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
        "pump_curve",
        "power",
        "base_speed",
        "speed_pattern",
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


types = {
    "BASE": {
        "name": QVariant.String,
        "node_type": QVariant.String,
        "link_type": QVariant.String,
        "elevation": QVariant.Double,
        "base_demand": QVariant.Double,
        "demand_pattern": QVariant.String,
        "emitter_coefficient": QVariant.Double,
        "init_level": QVariant.Double,
        "min_level": QVariant.Double,
        "max_level": QVariant.Double,
        "diameter": QVariant.Double,
        "min_vol": QVariant.Double,
        "vol_curve": QVariant.String,
        "overflow": QVariant.Bool,
        "base_head": QVariant.Double,
        "head_pattern": QVariant.String,
        "start_node_name": QVariant.String,
        "end_node_name": QVariant.String,
        "length": QVariant.Double,
        "roughness": QVariant.Double,
        "minor_loss": QVariant.Double,
        "initial_status": QVariant.String,
        "check_valve": QVariant.Bool,
        "pump_type": QVariant.String,
        "pump_curve": QVariant.String,
        "power": QVariant.Double,
        "base_speed": QVariant.Double,
        "speed_pattern": QVariant.String,
        "initial_setting": QVariant.Double,
        "valve_type": QVariant.String,
    },
    "QUALITY": {
        "initial_quality": QVariant.Double,
        "mixing_fraction": QVariant.Double,
        "mixing_model": QVariant.String,
        "bulk_coeff": QVariant.Double,
        "wall_coeff": QVariant.Double,
    },
    "PRESSUREDEPENDENT": {
        "minimum_pressure": QVariant.Double,
        "required_pressure": QVariant.Double,
        "pressure_exponent": QVariant.Double,
    },
    "ENERGY": {
        "efficiency": QVariant.Double,
        "energy_pattern": QVariant.String,
        "energy_price": QVariant.Double,
    },
}
