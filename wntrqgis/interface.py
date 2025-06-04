"""
This module contains the interfaces for for converting between WNTR and QGIS, both model layers and simulation results.
"""

from __future__ import annotations

import ast
import enum
import functools
import importlib
import itertools
import logging
import math
import pathlib
import warnings
from typing import TYPE_CHECKING, Any, Literal, cast

from qgis.core import (
    NULL,
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsDistanceArea,
    QgsFeature,
    QgsFeatureRequest,
    QgsFeatureSink,
    QgsFeatureSource,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPoint,
    QgsPointXY,
    QgsProject,
    QgsSpatialIndex,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QMetaType, QVariant

import wntrqgis.style
from wntrqgis.elements import (
    ElementFamily,
    Field,
    FieldGroup,
    FlowUnit,
    HeadlossFormula,
    ModelLayer,
    PumpTypes,
    ResultLayer,
    ValveType,
    _AbstractValueMap,
)
from wntrqgis.i18n import tr

if TYPE_CHECKING:  # pragma: no cover
    import wntr  # noqa
    import pandas as pd  # noqa
    import numpy as np  # noqa
    from numpy.typing import ArrayLike

logger = logging.getLogger(__name__)

QGIS_VERSION_DISTANCE_UNIT_IN_QGIS = 33000
QGIS_DISTANCE_UNIT_METERS = (
    Qgis.DistanceUnit.Meters if Qgis.versionInt() >= QGIS_VERSION_DISTANCE_UNIT_IN_QGIS else QgsUnitTypes.DistanceMeters
)
USE_QMETATYPE = Qgis.versionInt() >= 33800  # noqa: PLR2004


def needs_wntr_pandas(func):
    """This decorator loads numpy, pandas and wntr.

    Delayed loading means this module can be imported without throwing error if they don't exist"""

    @functools.wraps(func)
    def check_wntr(*args, **kwargs):
        if "wntr" not in globals():
            importlib.invalidate_caches()
            import numpy as np
            import pandas as pd
            import wntr

            globals()["wntr"] = wntr
            globals()["pd"] = pd
            globals()["np"] = np

        return func(*args, **kwargs)

    return check_wntr


@needs_wntr_pandas
class _Converter:
    """Manages conversion to and from SI units

    Args:
        flow_units: The set of units which will be converted to/from (or SI units for no conversion)
        headloss_formula: Used to determine how to handle conversion of the roughness coefficient
    """

    def __init__(
        self,
        flow_units: Literal["LPS", "LPM", "MLD", "CMH", "CFS", "GPM", "MGD", "IMGD", "AFD", "SI"],
        headloss_formula: HeadlossFormula,
    ):
        try:
            self._flow_units = wntr.epanet.FlowUnits[flow_units.upper()]
        except KeyError as e:
            raise UnitError(e) from None

        self._darcy_weisbach = headloss_formula is HeadlossFormula.DARCY_WEISBACH

    def to_si(
        self,
        value: float | ArrayLike | dict,
        field: Field | wntr.epanet.HydParam | wntr.epanet.QualParam,
        layer: ModelLayer | ResultLayer | None = None,
    ):
        conversion_param = self._get_wntr_conversion_param(field, layer)

        if not conversion_param:
            return value

        return wntr.epanet.util.to_si(
            self._flow_units, value, param=conversion_param, darcy_weisbach=self._darcy_weisbach
        )

    def from_si(
        self,
        value: float | ArrayLike | dict,
        field: Field | wntr.epanet.HydParam | wntr.epanet.QualParam,
        layer: ModelLayer | ResultLayer | None = None,
    ):
        conversion_param = self._get_wntr_conversion_param(field, layer)

        if not conversion_param:
            return value

        return wntr.epanet.util.from_si(
            self._flow_units, value, param=conversion_param, darcy_weisbach=self._darcy_weisbach
        )

    def _get_wntr_conversion_param(
        self, field: Field | wntr.epanet.HydParam | wntr.epanet.QualParam, layer: ModelLayer | ResultLayer | None = None
    ) -> wntr.epanet.QualParam | wntr.epanet.HydParam | None:
        QualParam = wntr.epanet.QualParam  # noqa
        HydParam = wntr.epanet.HydParam  # noqa

        if isinstance(field, (HydParam, QualParam)):
            return field

        if field.python_type is not float:
            return None

        if field is Field.ELEVATION:
            return HydParam.Elevation
        if field is Field.BASE_DEMAND or field is Field.DEMAND:
            return HydParam.Demand
        if field is Field.EMITTER_COEFFICIENT:
            return HydParam.EmitterCoeff
        if field in [Field.INITIAL_QUALITY, Field.QUALITY]:
            return QualParam.Quality
        if field in [Field.MINIMUM_PRESSURE, Field.REQUIRED_PRESSURE, Field.PRESSURE]:
            return HydParam.Pressure
        if field in [
            Field.INIT_LEVEL,
            Field.MIN_LEVEL,
            Field.MAX_LEVEL,
            Field.BASE_HEAD,
            Field.HEAD,
        ]:
            return HydParam.HydraulicHead
        if field is Field.DIAMETER and layer is ModelLayer.TANKS:
            return HydParam.TankDiameter
        if field is Field.DIAMETER:
            return HydParam.PipeDiameter
        if field is Field.MIN_VOL:
            return HydParam.Volume
        if field is Field.BULK_COEFF:
            return QualParam.BulkReactionCoeff
        if field is Field.LENGTH:
            return HydParam.Length
        if field is Field.ROUGHNESS:
            return HydParam.RoughnessCoeff
        if field is Field.WALL_COEFF:
            return QualParam.WallReactionCoeff
        if field is Field.POWER:
            return HydParam.Power
        if field is Field.FLOWRATE:
            return HydParam.Flow
        if field is Field.HEADLOSS:
            if layer is ModelLayer.PIPES:
                return HydParam.HeadLoss
            return HydParam.HydraulicHead
        if field is Field.VELOCITY:
            return HydParam.Velocity

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

        raise ValueError(field)


@needs_wntr_pandas
def to_qgis(
    wn: wntr.network.WaterNetworkModel | pathlib.Path | str,
    results: wntr.sim.SimulationResults | None = None,
    crs: QgsCoordinateReferenceSystem | str | None = None,
    units: Literal["LPS", "LPM", "MLD", "CMH", "CFS", "GPM", "MGD", "IMGD", "AFD", "SI"] | None = None,
    # layers: str | None = None,
    # fields: list | None = None,
    # filename: str | None = None,
) -> dict[str, QgsVectorLayer]:
    """Write from WNTR network model to QGIS Layers

    Args:
        wn: the water network model, or a path (string or path object) to an input file
        results: simulation results, if any.
        crs: The coordinate Reference System of the coordinates in the wntr model / .inp file.
        units: the set of units to write the layers using.

    """

    if isinstance(wn, (str, pathlib.Path)):
        wn = wntr.network.WaterNetworkModel(str(wn))

    writer = Writer(wn, results, units)
    map_layers: dict[str, QgsVectorLayer] = {}

    if crs:
        crs_object = QgsCoordinateReferenceSystem(crs)
        if not crs_object.isValid():
            msg = tr("CRS {crs} is not valid.").format(crs=crs)
            raise ValueError(msg)
    else:
        crs_object = QgsCoordinateReferenceSystem()

    model_layers: list[ModelLayer | ResultLayer] = list(ResultLayer if results else ModelLayer)
    for model_layer in model_layers:
        layer = QgsVectorLayer(
            "Point" if model_layer.qgs_wkb_type is QgsWkbTypes.Point else "LineString",
            model_layer.friendly_name,
            "memory",
        )
        layer.setCrs(crs_object)
        data_provider = layer.dataProvider()
        data_provider.addAttributes(writer.get_qgsfields(model_layer))
        writer.write(model_layer, data_provider)

        layer.updateFields()
        layer.updateExtents()
        wntrqgis.style.style(layer, model_layer, theme="extended" if results and wn.options.time.duration else None)
        QgsProject.instance().addMapLayer(layer)
        map_layers[model_layer.name] = layer

    return map_layers


@needs_wntr_pandas
class Writer:
    """Writes to QGIS layers (feature sinks) from a WNTR water network model, and optionally WNTR simulation results.

    Args:
        wn: The WNTR water network model that we will write from
        results: The simulation results. Default is that there are no simulation results.
        units: The units that it should be written in values include ``"LPS"``, ``"GPM"`` etc.
            Default is to use the units within the WaterNetworkModel options

    """

    def __init__(
        self,
        wn: wntr.network.WaterNetworkModel,
        results: wntr.sim.SimulationResults | None = None,
        units: Literal["LPS", "LPM", "MLD", "CMH", "CFS", "GPM", "MGD", "IMGD", "AFD", "SI"] | None = None,
    ) -> None:
        if not units:
            units = wn.options.hydraulic.inpfile_units
            units_friendly_name = FlowUnit[units].friendly_name
            logger.warning(
                tr(
                    "No units specified. Will use the value specified in WaterNetworkModel object: {units_friendly_name}"  # noqa: E501
                ).format(units_friendly_name=units_friendly_name)
            )

        self._converter = _Converter(units, HeadlossFormula(wn.options.hydraulic.headloss))

        self._timestep = None
        if not wn.options.time.duration:
            self._timestep = 0

        self._types: dict[ResultLayer, pd.Series] = {}
        self._types[ResultLayer.LINKS] = pd.Series({link_name: link.link_type for link_name, link in wn.links()})
        self._types[ResultLayer.NODES] = pd.Series({node_name: node.node_type for node_name, node in wn.nodes()})

        if results:
            self._result_dfs = self._get_results_dfs(results)
        else:
            self._model_dfs = self._get_model_dfs(wn)

        self._geometries = self._get_geometries(wn)

        field_group = FieldGroup.BASE | _get_field_groups(wn)

        self.fields: list[Field]
        """A list of field names to be written

        * The default set of fields will depend on ``wn`` and ``results``
        * When writing only those fields related to the layer bei_ng written will be used.
        """
        if results:
            self.fields = [Field.NAME]
            self.fields.extend([field for field in Field if field.field_group & field_group])
        else:
            self.fields = [field for field in Field if field.field_group & field_group]

    def _get_geometries(self, wn: wntr.network.WaterNetworkModel) -> dict[ElementFamily, dict[str, QgsGeometry]]:
        """As the WNTR simulation result do not contain any geometry information it is necessary to load them

        This function loads the geometries from a WaterNetworkModel"""
        geometries: dict[ElementFamily, dict[str, QgsGeometry]] = {ElementFamily.NODE: {}, ElementFamily.LINK: {}}

        name: str
        node: wntr.network.elements.Node
        for name, node in wn.nodes():
            geometries[ElementFamily.NODE][name] = QgsGeometry(QgsPoint(*node.coordinates))

        link: wntr.network.elements.Link
        for name, link in wn.links():
            point_list = [
                QgsPoint(*vertex)
                for vertex in [
                    link.start_node.coordinates,
                    *link.vertices,
                    link.end_node.coordinates,
                ]
            ]
            geometries[ElementFamily.LINK][name] = QgsGeometry.fromPolyline(point_list)

        return geometries

    def get_qgsfields(self, layer: ModelLayer | ResultLayer) -> QgsFields:
        """Get the set of QgsFields that will be written by 'write'.

        This set of fields will need to be used when creating any sink/layer
        which will be written to by write_to_sink

        Args:
            layer: 'JUNCTIONS','PIPES','LINKS' etc.

        Returns:
            QgsFields: The set of fields to be written.
        """
        if isinstance(layer, ResultLayer):
            layer_df = self._result_dfs.get(layer, pd.DataFrame())
        else:
            layer_df = self._model_dfs.get(layer, pd.DataFrame())

        field_names = ["name"]  # get this as first column
        field_names.extend(field.name for field in self.fields if field in layer.wq_fields())
        field_names.extend(layer_df.columns.to_list())
        field_names = list(dict.fromkeys(field_names))  # de-duplicate

        for ignore_key in ["node_type", "link_type"]:
            if ignore_key in field_names:
                field_names.remove(ignore_key)

        layer_df = layer_df.convert_dtypes(convert_integer=False)
        dtypes = layer_df.dtypes

        qgs_fields = QgsFields()  # nice constructor didn't arrive until qgis 3.40

        for f in field_names:
            is_list_field = False
            try:
                dtype = Field[f.upper()].python_type
                is_list_field = bool(Field[f.upper()].field_group & FieldGroup.LIST_IN_EXTENDED_PERIOD)
            except KeyError:
                dtype = dtypes[f]

            if is_list_field and self._timestep is None:
                qgs_fields.append(
                    QgsField(
                        f.lower(),
                        self._get_qgs_field_type(list),
                        subType=self._get_qgs_field_type(float),
                    )
                )
            else:
                qgs_fields.append(
                    QgsField(
                        f.lower(),
                        self._get_qgs_field_type(dtype),
                    )
                )
        return qgs_fields

    def write(self, layer: ModelLayer | ResultLayer, sink: QgsFeatureSink) -> None:
        """Write a fields from a layer to a QGIS feature sink

        Args:
            layer: which layer should be written to the sink: 'JUNCTIONS','PIPES','LINKS' etc.
            sink: the sink to write to
        """
        field_names = self.get_qgsfields(layer).names()

        if isinstance(layer, ResultLayer):
            layer_df = self._result_dfs.get(layer, pd.DataFrame())
        else:
            layer_df = self._model_dfs.get(layer, pd.DataFrame())

        missing_cols = list(set(field_names) - set(layer_df.columns))

        if len(missing_cols) > 0:
            layer_df[missing_cols] = NULL

        ordered_df = layer_df[field_names]

        attribute_series = pd.Series(
            ordered_df.to_numpy().tolist(),
            index=ordered_df.index,
        )

        geometries = self._geometries[layer.element_family]

        for name, attributes in attribute_series.items():
            f = QgsFeature()
            f.setGeometry(geometries[name])
            f.setAttributes(
                [value if not (isinstance(value, (int, float)) and math.isnan(value)) else NULL for value in attributes]
            )
            sink.addFeature(f, QgsFeatureSink.FastInsert)

    def _get_model_dfs(self, wn: wntr.network.WaterNetworkModel) -> dict[ModelLayer, pd.DataFrame]:
        wn_dict = wn.to_dict()

        dfs: dict[ModelLayer, pd.DataFrame] = {}

        df_nodes = pd.DataFrame(wn_dict["nodes"])
        if len(df_nodes) > 0:
            df_nodes = df_nodes.set_index("name", drop=False)
            df_nodes = df_nodes.drop(
                columns=[
                    "coordinates",
                    "demand_timeseries_list",
                    "leak",
                    "leak_area",
                    "leak_discharge_coeff",
                ],
                errors="ignore",
            )
            dfs[ModelLayer.JUNCTIONS] = df_nodes[df_nodes["node_type"] == "Junction"].dropna(axis=1, how="all")
            dfs[ModelLayer.TANKS] = df_nodes[df_nodes["node_type"] == "Tank"].dropna(axis=1, how="all")
            dfs[ModelLayer.RESERVOIRS] = df_nodes[df_nodes["node_type"] == "Reservoir"].dropna(axis=1, how="all")

        df_links = pd.DataFrame(wn_dict["links"])
        if len(df_links) > 0:
            df_links = df_links.set_index("name", drop=False)
            df_links = df_links.drop(
                columns=["start_node_name", "end_node_name", "vertices", "initial_quality"],
                errors="ignore",
            )
            dfs[ModelLayer.PIPES] = df_links[df_links["link_type"] == "Pipe"].dropna(axis=1, how="all")
            dfs[ModelLayer.PUMPS] = df_links[df_links["link_type"] == "Pump"].dropna(axis=1, how="all")
            dfs[ModelLayer.VALVES] = df_links[df_links["link_type"] == "Valve"].dropna(axis=1, how="all")

        patterns = _Patterns(wn)
        curves = _Curves(wn, self._converter)

        for lyr, df in dfs.items():
            if len(df) == 0:
                continue

            if (
                lyr in [ModelLayer.JUNCTIONS, ModelLayer.RESERVOIRS, ModelLayer.TANKS]
                and "initial_quality" in df
                and (df["initial_quality"] == 0.0).all()
            ):
                df.drop(columns=["initial_quality"], inplace=True)  # noqa: PD002

            if lyr is ModelLayer.JUNCTIONS:
                # Special case for demands
                df["base_demand"] = wn.query_node_attribute("base_demand", node_type=wntr.network.model.Junction)

                # 'demand_pattern' didn't exist on node prior to wntr 1.3.0 so we have to go searching:
                df["demand_pattern"] = wn.query_node_attribute(
                    "demand_timeseries_list", node_type=wntr.network.model.Junction
                ).apply(lambda dtl: patterns.get(dtl.pattern_list()[0]))

            elif lyr is ModelLayer.RESERVOIRS:
                if "head_pattern_name" in df:
                    df.loc[:, "head_pattern"] = df["head_pattern_name"].apply(patterns.get)
                    df.drop(columns="head_pattern_name", inplace=True)  # noqa: PD002

            elif lyr is ModelLayer.TANKS:
                if "vol_curve_name" in df:
                    df.loc[:, "vol_curve"] = df["vol_curve_name"].apply(curves.get)
                    df.drop(columns="vol_curve_name", inplace=True)  # noqa: PD002

            elif lyr is ModelLayer.PUMPS:
                # not all pumps will have a pump curve (power pumps)!
                if "pump_curve_name" in df:
                    df["pump_curve"] = df["pump_curve_name"].apply(curves.get)
                    df.drop(columns="pump_curve_name", inplace=True)  # noqa: PD002

                if "speed_pattern_name" in df:
                    df["speed_pattern"] = df["speed_pattern_name"].apply(patterns.get)
                    df.drop(columns="speed_pattern_name", inplace=True)  # noqa: PD002
                # 'energy pattern' is not called energy pattern name!
                if "energy_pattern" in df:
                    df["energy_pattern"] = df["energy_pattern"].apply(patterns.get)

                if "efficiency" in df:
                    df["efficiency"] = df["efficiency"].apply(lambda x: curves.get(x["name"]))

            elif lyr is ModelLayer.VALVES:
                p_valves_setting = df["valve_type"].isin(["PRV", "PSV", "PBV"]), "initial_setting"
                df.loc[p_valves_setting] = self._converter.from_si(
                    df.loc[p_valves_setting].to_numpy(), wntr.epanet.HydParam.Pressure
                ).round(5)
                df.loc[df["valve_type"] == "FCV", "initial_setting"] = self._converter.from_si(
                    df.loc[df["valve_type"] == "FCV", "initial_setting"].to_numpy(), wntr.epanet.HydParam.Flow
                ).round(5)
                if "headloss_curve" in df:
                    df.loc[df["valve_type"] == "GPV", "headloss_curve"] = df.loc[
                        df["valve_type"] == "GPV", "headloss_curve_name"
                    ].apply(curves.get)

            for fieldname in df.select_dtypes(include=[np.floating]):
                try:
                    field = Field[str(fieldname).upper()]
                except KeyError:
                    continue
                converted_array = self._converter.from_si(df[fieldname].to_numpy(), field, lyr)
                df[fieldname] = converted_array.round(5)

        return dfs

    def _get_results_dfs(self, results: wntr.sim.SimulationResults) -> dict[ResultLayer, pd.DataFrame]:
        result_df = {}
        for layer in ResultLayer:
            results_dfs = results.node if layer is ResultLayer.NODES else results.link

            result_df[layer] = self._process_results_layer(layer, results_dfs)

        return result_df

    def _process_results_layer(self, layer: ResultLayer, results_dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
        output_attributes: dict[str, pd.Series] = {}

        for field in layer.wq_fields():
            converted_df = self._convert_result_df(results_dfs[field.value].copy(), field)

            if self._timestep is not None:
                output_attributes[field.value] = converted_df.iloc[self._timestep]
            else:
                lists = converted_df.transpose().to_numpy().tolist()
                output_attributes[field.value] = pd.Series(lists, index=converted_df.columns)

        output_attributes["name"] = output_attributes[field.value].index.to_series()

        return pd.DataFrame(output_attributes, index=output_attributes[field.value].index)

    def _convert_result_df(self, df: pd.DataFrame, field: Field) -> pd.DataFrame:
        "Convert a results dataframe, taking special care with 'headloss' which for pipes doubles as 'unit headloss'"
        converted_df: pd.DataFrame
        if field is Field.HEADLOSS:
            converted_df = df
            type_series = self._types[ResultLayer.LINKS].reindex(converted_df.columns)

            converted_df.loc[:, type_series == "Pipe"] = self._converter.from_si(
                converted_df.loc[:, type_series == "Pipe"], field, ModelLayer.PIPES
            )
            converted_df.loc[:, type_series != "Pipe"] = self._converter.from_si(
                converted_df.loc[:, type_series != "Pipe"], field
            )

        else:
            converted_df = self._converter.from_si(df, field)

        converted_df = converted_df.round(2)

        return converted_df

    def _get_qgs_field_type(self, dtype: Any) -> QMetaType | QVariant:
        if dtype is list:  # Must be checked before string type
            return QMetaType.Type.QVariantList if USE_QMETATYPE else QVariant.List

        try:
            is_abstract_value_map = issubclass(_AbstractValueMap, dtype)
        except TypeError:
            is_abstract_value_map = False

        if is_abstract_value_map or pd.api.types.is_string_dtype(dtype):
            return QMetaType.Type.QString if USE_QMETATYPE else QVariant.String

        if pd.api.types.is_float_dtype(dtype):
            return QMetaType.Type.Double if USE_QMETATYPE else QVariant.Double

        if pd.api.types.is_bool_dtype(dtype):
            return QMetaType.Type.Bool if USE_QMETATYPE else QVariant.Bool

        if pd.api.types.is_integer_dtype(dtype):
            return QMetaType.Type.Int if USE_QMETATYPE else QVariant.Int

        raise KeyError(f"Couldn't get qgs field type for {dtype}")  # noqa: EM102, TRY003


class _SpatialIndex:
    def __init__(self) -> None:
        self._node_spatial_index = QgsSpatialIndex()
        self._nodelist: list[tuple[QgsPointXY, str]] = []

    def add_node(self, geometry: QgsGeometry, element_name: str):
        point = geometry.asPoint()
        feature_id = len(self._nodelist)
        self._nodelist.append((point, element_name))
        self._node_spatial_index.addFeature(feature_id, geometry.boundingBox())

    def _snapper(self, line_vertex_point: QgsPointXY, original_length: float):
        nearest = self._node_spatial_index.nearestNeighbor(line_vertex_point)
        matched_node_point, matched_node_name = self._nodelist[nearest[0]]
        snap_distance = matched_node_point.distance(line_vertex_point)
        if snap_distance > original_length * 0.1:
            msg = tr("nearest node to snap to is too far ({matched_node_name}).").format(
                matched_node_name=matched_node_name
            )
            # Line length:{original_length} Snap Distance: {snap_distance}"
            raise RuntimeError(msg)
        return (matched_node_point, matched_node_name)

    def snap_link(
        self,
        geometry: QgsGeometry,
    ):
        try:
            vertices = geometry.asPolyline()
        except TypeError:
            msg = tr("All links must be single part lines")
            raise RuntimeError(msg) from None
        except ValueError:
            msg = tr("All links must have valid geometry")
            raise RuntimeError(msg) from None

        start_point = vertices.pop(0)
        end_point = vertices.pop()
        original_length = geometry.length()
        try:
            (new_start_point, start_node_name) = self._snapper(start_point, original_length)
            (new_end_point, end_node_name) = self._snapper(end_point, original_length)
        except RuntimeError as e:
            msg = tr("couldn't snap: {exception}").format(exception=e)
            raise RuntimeError(msg) from None

        if start_node_name == end_node_name:
            msg = tr("connects to the same node on both ends ({start_node_name})").format(
                start_node_name=start_node_name
            )
            raise RuntimeError(msg)

        snapped_geometry = QgsGeometry.fromPolylineXY([new_start_point, *vertices, new_end_point])

        return snapped_geometry, start_node_name, end_node_name


@needs_wntr_pandas
class _Patterns:
    def __init__(self, wn: wntr.network.model.WaterNetworkModel) -> None:
        self._name_iterator = map(str, itertools.count(2))
        self._existing_patterns: dict[tuple, str] = {}
        self._wn = wn

    def add(self, pattern) -> str | None:
        input_pattern = pattern
        if isinstance(pattern, str):
            pattern = cast(str, pattern)
            pattern = pattern.strip().split()

        try:
            pattern_list = [float(item) for item in pattern]
        except (ValueError, TypeError):
            raise ValueError(input_pattern) from None

        if len(pattern_list) == 0:
            return None

        pattern_tuple = tuple(pattern_list)

        if existing_pattern_name := self._existing_patterns.get(pattern_tuple):
            return existing_pattern_name

        name = next(self._name_iterator)
        self._wn.add_pattern(name=name, pattern=pattern_list)
        self._existing_patterns[pattern_tuple] = name
        return name

    def add_all(self, pattern_series: pd.Series | Any, layer: ModelLayer, pattern_type: Field) -> pd.Series | None:
        if not isinstance(pattern_series, pd.Series):
            return None
        # try:
        #     pattern_map = {
        #         pattern: self.add(pattern, layer_name, pattern_name) for pattern in pattern_series.dropna().unique()
        #     }
        # except TypeError:
        try:
            return pattern_series.map(self.add, na_action="ignore")
        except ValueError as e:
            raise PatternError(e, layer, pattern_type) from None
        # return pattern_series.map(pattern_map)

    def get(self, pattern: wntr.network.elements.Pattern | str | None) -> str | None:
        if isinstance(pattern, str):
            pattern = self._wn.get_pattern(pattern)
        if isinstance(pattern, wntr.network.elements.Pattern):
            return " ".join(map(str, pattern.multipliers))
        return None


@needs_wntr_pandas
class _Curves:
    def __init__(self, wn: wntr.network.WaterNetworkModel, converter: _Converter) -> None:
        self._wn = wn
        self._name_iterator = map(str, itertools.count(1))
        self._converter = converter

    class Type(enum.Enum):
        HEAD = "HEAD"
        EFFICIENCY = "EFFICIENCY"
        VOLUME = "VOLUME"
        HEADLOSS = "HEADLOSS"

    def _add_one(self, curve_string: Any, curve_type: _Curves.Type) -> str | None:
        if not isinstance(curve_string, str):
            raise CurveError(curve_string, curve_type)

        if curve_string.strip() == "":
            return None

        try:
            curve_points_input: list = ast.literal_eval(curve_string)
        except Exception:  # noqa: BLE001
            raise CurveError(curve_string, curve_type) from None

        curve_points = []
        try:
            for point in curve_points_input:
                if len(point) != 2:  # noqa: PLR2004
                    raise CurveError(curve_string, curve_type)
                curve_points.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError):
            raise CurveError(curve_string, curve_type) from None

        if not len(curve_points):
            raise CurveError(curve_string, curve_type) from None
        try:
            curve_points = self._convert_points(curve_points, curve_type, self._converter.to_si)
        except TypeError as e:
            raise CurveError(curve_string, curve_type) from e

        name = next(self._name_iterator)
        self._wn.add_curve(name=name, curve_type=curve_type.value, xy_tuples_list=curve_points)
        return name

    def _add_all(self, curve_series: pd.Series, curve_type: _Curves.Type) -> pd.Series | None:
        curve_map = {curve: self._add_one(curve, curve_type) for curve in curve_series.dropna().unique()}
        return curve_series.map(curve_map, na_action="ignore")

    add_head = functools.partialmethod(_add_all, curve_type=Type.HEAD)
    add_efficiency = functools.partialmethod(_add_all, curve_type=Type.EFFICIENCY)
    add_volume = functools.partialmethod(_add_all, curve_type=Type.VOLUME)
    add_headloss = functools.partialmethod(_add_all, curve_type=Type.HEADLOSS)

    def get(self, curve_name: str) -> str | None:
        curve: wntr.network.elements.Curve = self._wn.get_curve(curve_name)

        converted_points = self._convert_points(curve.points, _Curves.Type(curve.curve_type), self._converter.from_si)
        return repr(converted_points)

    def _convert_points(self, points: list, curve_type: _Curves.Type, conversion_function) -> list[tuple[float, float]]:
        converted_points: list[tuple[float, float]] = []
        HydParam = wntr.epanet.HydParam  # noqa: N806

        if curve_type is _Curves.Type.VOLUME:
            for point in points:
                x = conversion_function(point[0], HydParam.Length)
                y = conversion_function(point[1], HydParam.Volume)
                converted_points.append((x, y))
        elif curve_type is _Curves.Type.HEAD:
            for point in points:
                x = conversion_function(point[0], HydParam.Flow)
                y = conversion_function(point[1], HydParam.HydraulicHead)
                converted_points.append((x, y))
        elif curve_type is _Curves.Type.EFFICIENCY:
            for point in points:
                x = conversion_function(point[0], HydParam.Flow)
                y = point[1]
                converted_points.append((x, y))
        elif curve_type is _Curves.Type.HEADLOSS:
            for point in points:
                x = conversion_function(point[0], HydParam.Flow)
                y = conversion_function(point[1], HydParam.HydraulicHead)
                converted_points.append((x, y))
        else:
            raise KeyError("Curve type not specified")  # noqa: EM101, TRY003 # pragma: no cover
        return converted_points


@needs_wntr_pandas
def from_qgis(
    layers: dict[Literal["JUNCTIONS", "RESERVOIRS", "TANKS", "PIPES", "VALVES", "PUMPS"], QgsFeatureSource],
    units: Literal["LPS", "LPM", "MLD", "CMH", "CFS", "GPM", "MGD", "IMGD", "AFD", "SI"],
    headloss: Literal["H-W", "D-W", "C-M"] | None = None,
    wn: wntr.network.WaterNetworkModel | None = None,
    project: QgsProject | None = None,
    crs: QgsCoordinateReferenceSystem | str | None = None,
) -> wntr.network.WaterNetworkModel:
    """Read from QGIS layers or feature sources to a WNTR ``WaterNetworkModel``

    Args:
        layers: layers to read from
        units: The flow unit set that the layers being read use.
        headloss: the headloss formula to use
            (H-W for Hazen Williams, D-W for Darcy Weisbach, or C-M for Chezy-Manning).
            Must be set if there is no wn.
            If wn is provided, headloss in wn.options.hydraulic.headloss will be used instead.
        wn: The `WaterNetworkModel` that the layers will be read into. Will create a new model if `None`.
        project: QgsProject instance, if `None` the current `QgsProject.instance()` will be used.
        crs: All geometry will be transformed into this coordinate reference system.
            If not set the geometry of the first layer will be used.

    """

    if wn:
        if headloss:
            msg = tr(
                "Cannot set headloss when wn is set. Set the headloss in the wn.options.hydraulic.headloss instead"
            )
            raise ValueError(msg)
        headloss_formula_type = HeadlossFormula(wn.options.hydraulic.headloss)
    else:
        wn = wntr.network.WaterNetworkModel()

        if not headloss:
            msg = tr("headloss must be set if wn is not set: possible values are: H-W, D-W, C-M")
            raise ValueError(msg)
        headloss_formula_type = HeadlossFormula(headloss)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=UserWarning,
                message="Changing the headloss formula from H-W to D-W will not change",
            )
            wn.options.hydraulic.headloss = headloss

    # try:
    #     flow_units = wntr.epanet.FlowUnits[str(units).upper()]
    # except KeyError as e:
    #     msg = f"Units {e} is not a known set of units. Possible units are: " + ", ".join(FlowUnit._member_names_)
    #     raise ValueError(msg) from None

    unit_conversion = _Converter(units, headloss_formula_type)

    reader = _FromGis(unit_conversion, project)
    if crs:
        reader.crs = QgsCoordinateReferenceSystem(crs)

    try:
        model_layers = {}
        for layer_name, layer in layers.items():
            model_layers.update({ModelLayer(str(layer_name).upper()): layer})
    except ValueError:
        msg = tr("'{layer_name}' is not a valid layer type.").format(layer_name=layer_name)
        raise ValueError(msg) from None

    reader.add_features_to_network_model(model_layers, wn)

    return wn


@needs_wntr_pandas
class _FromGis:
    """Read from QGIS feature sources / layers to a WNTR model"""

    def __init__(
        self,
        converter: _Converter,
        project: QgsProject | None = None,
        # transform_context: QgsCoordinateTransformContext | None = None,
        # ellipsoid: str | None = "EPSG:7030",
    ):
        if not project:
            project = QgsProject.instance()

        # self._transform_context = (
        #     transform_context if transform_context is not None else QgsCoordinateTransformContext()
        # )
        # self._ellipsoid = ellipsoid
        self._transform_context = project.transformContext()
        self._ellipsoid = project.ellipsoid()
        self._converter = converter
        self.crs = None

    @property
    def crs(self) -> QgsCoordinateReferenceSystem | None:
        "The coordinate reference system source features will be transformed to"
        return self._crs

    @crs.setter
    def crs(self, crs: QgsCoordinateReferenceSystem | None):
        self._crs = crs
        if crs:
            self._measurer = QgsDistanceArea()
            self._measurer.setSourceCrs(crs, self._transform_context)
            self._measurer.setEllipsoid(self._ellipsoid)

    def add_features_to_network_model(
        self, feature_sources: dict[ModelLayer, QgsFeatureSource], wn: wntr.network.WaterNetworkModel
    ) -> None:
        """Do the conversion to WNTR

        Args:
            feature_sources: dictionary of layers/feature sources from which to take features
            wn: The model to which features should be added

        Raises:
            NetworkModelError: if the network cannot be created
        """

        self.patterns = _Patterns(wn)
        self.curves = _Curves(wn, self._converter)
        self._spatial_index = _SpatialIndex()

        node_dfs: list[pd.DataFrame] = []
        link_dfs: list[pd.DataFrame] = []

        shapefile_name_map = {wq_field.name[:10].lower(): wq_field.name.lower() for wq_field in Field}

        for model_layer in ModelLayer:
            source = feature_sources.get(model_layer)
            if source is None:
                continue

            if not self.crs:
                self.crs = source.sourceCrs()

            source_df = self._source_to_df(source)

            if not source_df.shape[0]:
                continue

            source_df.columns = [shapefile_name_map.get(col, col) for col in source_df.columns]

            if model_layer in [ModelLayer.JUNCTIONS, ModelLayer.RESERVOIRS, ModelLayer.TANKS]:
                source_df["node_type"] = model_layer.name[:-1].title()
                node_dfs.append(source_df)
            else:
                source_df["link_type"] = model_layer.name[:-1].title()
                link_dfs.append(source_df)

        try:
            node_df = pd.concat(node_dfs, sort=False, ignore_index=True)
        except ValueError:
            msg = tr("There are no nodes in the model")
            raise NetworkModelError(msg) from ValueError
        try:
            link_df = pd.concat(link_dfs, sort=False, ignore_index=True)
        except ValueError:
            msg = tr("There are no links in the model")
            raise NetworkModelError(msg) from ValueError

        node_df = self._fix_column_types(node_df)
        link_df = self._fix_column_types(link_df)

        self._fill_names(node_df)
        self._fill_names(link_df)

        self._check_for_duplicate_names(node_df)
        self._check_for_duplicate_names(link_df)

        node_df = self._convert_dataframe(node_df, ModelLayer.TANKS)  # hack as I know tanks is needed for diameter
        link_df = self._convert_dataframe(link_df)

        node_df = self._process_node_geometry(node_df)
        link_df = self._process_link_geometry(link_df)

        node_df = self._do_node_patterns_curves(node_df)
        link_df = self._do_link_patterns_curves(link_df)

        wn_dict: dict[str, Any] = {}
        wn_dict["nodes"] = self._to_dict(node_df)
        wn_dict["links"] = self._to_dict(link_df)

        logging.getLogger("wntr.network.io").setLevel(logging.CRITICAL)
        try:
            wn = wntr.network.from_dict(wn_dict, wn)
        except Exception as e:
            raise WntrError(e) from e

    def _to_dict(self, df: pd.DataFrame) -> list[dict]:
        columns = df.columns.tolist()
        return [
            {k: v for k, v in zip(columns, m) if not (v is pd.NA or v != v or v is None)}  # noqa: PLR0124
            for m in df.itertuples(index=False, name=None)
        ]

    def _source_to_df(self, source: QgsFeatureSource):
        column_names = [name.lower() for name in source.fields().names()]
        column_names.append("geometry")

        feature_list: list[list] = []
        feature_request = QgsFeatureRequest().setDestinationCrs(self.crs, self._transform_context)
        ft: QgsFeature
        for ft in source.getFeatures(feature_request):
            attrs = [attr if attr != NULL else np.nan for attr in ft]
            geometry = ft.geometry()
            geometry.convertToSingleType()
            attrs.append(geometry)
            feature_list.append(attrs)
        return pd.DataFrame(feature_list, columns=column_names)

    def _fix_column_types(self, source_df: pd.DataFrame) -> pd.DataFrame:
        """For some file types, notably json, numbers might be imported as strings.

        Also, for boolean values that come in as number types (int or float), they must finish as nullable int.
          (wntr doesn't accept floats for bool)"""
        for column_name in source_df.columns:
            try:
                expected_type = Field[column_name.upper()].python_type
            except KeyError:
                continue

            try:
                if expected_type is float:
                    source_df[column_name] = pd.to_numeric(source_df[column_name])
                elif expected_type is bool:
                    source_df[column_name] = pd.to_numeric(source_df[column_name]).astype("Int64").astype("object")
            except (ValueError, TypeError) as e:
                msg = tr("Problem in column {column_name}: {exception}").format(column_name=column_name, exception=e)
                raise NetworkModelError(msg) from None
        return source_df

    def _convert_dataframe(self, source_df: pd.DataFrame, layer: ModelLayer | None = None) -> pd.DataFrame:
        for fieldname in source_df.select_dtypes(include=[np.number]):
            try:
                field = Field[str(fieldname).upper()]
            except KeyError:
                continue
            source_df[fieldname] = self._converter.to_si(source_df[fieldname].to_numpy(), field, layer)
        return source_df

    def _process_node_geometry(self, df: pd.DataFrame) -> pd.DataFrame:
        null_geometry = df.loc[:, "geometry"].map(lambda geometry: geometry.isNull()).sum()
        if null_geometry:
            msg = tr("in nodes, %n feature(s) have no geometry", "", null_geometry)
            raise NetworkModelError(msg)

        for geometry, name in df.loc[:, ["geometry", "name"]].itertuples(index=False):
            self._spatial_index.add_node(geometry, name)

        df.loc[:, "coordinates"] = df.loc[:, "geometry"].apply(self._get_point_coordinates)

        return df.drop(columns="geometry")

    def _process_link_geometry(self, link_df: pd.DataFrame) -> pd.DataFrame:
        null_geometry = link_df.loc[:, "geometry"].map(lambda geometry: geometry.isNull()).sum()
        if null_geometry:
            msg = tr("in links, %n feature(s) have no geometry", "", null_geometry)
            raise NetworkModelError(msg)

        snapped_data = []
        try:
            for geometry, name in link_df.loc[:, ["geometry", "name"]].itertuples(index=False):  # noqa: B007
                snapped_data.append(self._spatial_index.snap_link(geometry))
        except RuntimeError as e:
            msg = tr("problem snapping the feature {name}: {exception}").format(name=name, exception=e)
            raise NetworkModelError(msg) from None
        link_df[["geometry", "start_node_name", "end_node_name"]] = snapped_data

        link_df["vertices"] = link_df["geometry"].map(
            lambda geometry: [(v.x(), v.y()) for v in geometry.asPolyline()[1:-1]]
        )

        if "length" not in link_df.columns:
            link_df["length"] = np.nan
        pipes = link_df["link_type"] == "Pipe"
        link_df.loc[pipes, "length"] = self._process_pipe_length(link_df.loc[pipes])

        return link_df.drop(columns="geometry")

    def _process_pipe_length(self, pipe_df: pd.DataFrame) -> pd.Series:
        calculated_lengths: pd.Series = pipe_df.loc[:, "geometry"].map(self._get_length).astype("float")
        if calculated_lengths.isna().any():
            msg = tr(
                "cannot calculate length of %n pipe(s) (probably due to a problem with the selected coordinate reference system)",  # noqa: E501
                "",
                calculated_lengths.isna().sum(),
            )
            raise NetworkModelError(msg)

        attribute_lengths = pipe_df.loc[:, "length"]

        has_attr_length = attribute_lengths.notna()

        mismatch = ~np.isclose(
            calculated_lengths.loc[has_attr_length],
            attribute_lengths.loc[has_attr_length],
            rtol=0.05,
            atol=10,
        )

        if mismatch.any():
            examples = pd.concat(
                [pipe_df["name"], calculated_lengths, attribute_lengths],
                axis=1,
                ignore_index=True,
            )
            examples.columns = pd.Index(["name", "attribute_length", "calculated_length"])
            examples = examples.loc[has_attr_length].loc[mismatch]
            examples = examples.head(5)
            number_of_mismatches = mismatch.sum()
            msg = tr(
                "%n pipe(s) have very different attribute length vs measured length. First five are: ",
                "",
                number_of_mismatches,
            ) + ", ".join(
                examples.apply(
                    tr("{name} ({attribute_length:.0f} metres vs {calculated_length:.0f} metres)").format_map, axis=1
                )
            )
            logger.warning(msg)

        return attribute_lengths.fillna(calculated_lengths)

    def _fill_names(self, df: pd.DataFrame) -> None:
        if "name" not in df.columns:
            df["name"] = pd.NA

        df["name"] = df["name"].astype("string").str.strip()

        existing_names = set(df["name"].dropna())
        mask = (df["name"].isna()) | (df["name"] == "")
        number_of_names_required = mask.sum()

        name_iterator = map(str, itertools.count(1))
        valid_name_iterator = filter(lambda name: name not in existing_names, name_iterator)
        new_names = list(itertools.islice(valid_name_iterator, number_of_names_required))

        df.loc[mask, "name"] = new_names

    def _get_point_coordinates(self, geometry: QgsGeometry):
        point = geometry.constGet()
        return point.x(), point.y()

    def _get_length(self, geometry: QgsGeometry):
        length = self._measurer.measureLength(geometry)

        if self._measurer.lengthUnits() != QGIS_DISTANCE_UNIT_METERS:
            length = self._measurer.convertLengthMeasurement(length, QGIS_DISTANCE_UNIT_METERS)

        return length

    def _do_node_patterns_curves(self, node_df: pd.DataFrame) -> pd.DataFrame:
        for layer in [ModelLayer.JUNCTIONS, ModelLayer.TANKS, ModelLayer.RESERVOIRS]:
            layer_items = node_df["node_type"] == layer.field_type
            if layer_items.any():
                for field in layer.wq_fields():
                    if not field.field_group & FieldGroup.REQUIRED:
                        continue
                    if field.value not in node_df:
                        raise RequiredFieldError(layer, field)
                    if node_df.loc[layer_items, field.value].hasnans:
                        raise RequiredFieldError(layer, field)

        node_df["demand_pattern_name"] = self.patterns.add_all(
            node_df.get("demand_pattern"), ModelLayer.JUNCTIONS, Field.DEMAND_PATTERN
        )

        if "base_demand" in node_df.columns:
            has_demand = node_df.loc[:, "base_demand"].notna()

            node_df.loc[has_demand, "demand_timeseries_list"] = pd.Series(
                [
                    [{"base_val": demand[0], "pattern_name": (demand[1] if pd.notna(demand[1]) else None)}]
                    for demand in node_df.loc[has_demand, ["base_demand", "demand_pattern_name"]].itertuples(
                        index=False, name=None
                    )
                ]
            )

        # tanks volume curve
        if "vol_curve" in node_df:
            node_df["vol_curve_name"] = self.curves.add_volume(node_df["vol_curve"])

        # reservoir head pattern
        if "head_pattern" in node_df:
            node_df["head_pattern_name"] = self.patterns.add_all(
                node_df.get("head_pattern"), ModelLayer.RESERVOIRS, Field.HEAD_PATTERN
            )

        return node_df.drop(
            columns=["vol_curve", "head_pattern", "base_demand", "demand_pattern", "demand_pattern_name"],
            errors="ignore",
        )

    def _do_link_patterns_curves(self, link_df: pd.DataFrame) -> pd.DataFrame:
        valves = link_df["link_type"] == "Valve"

        if valves.any():
            try:
                link_df[Field.VALVE_TYPE.value] = link_df[Field.VALVE_TYPE.value].str.upper()
            except (KeyError, AttributeError):
                raise ValveTypeError from None

            if not link_df.loc[valves, Field.VALVE_TYPE.value].isin(ValveType._member_names_).all():
                raise ValveTypeError from None

            pressure_valves = link_df[Field.VALVE_TYPE.value].isin(
                [ValveType.PRV.name, ValveType.PSV.name, ValveType.PBV.name]
            )
            fcvs = link_df[Field.VALVE_TYPE.value] == ValveType.FCV.name
            tcvs = link_df[Field.VALVE_TYPE.value] == ValveType.TCV.name
            gpvs = link_df[Field.VALVE_TYPE.value] == ValveType.GPV.name

            if pressure_valves.any() or fcvs.any() or tcvs.any():
                if "initial_setting" not in link_df:
                    raise ValveInitialSettingError

                if link_df.loc[(pressure_valves | fcvs | tcvs), "initial_setting"].hasnans:
                    raise ValveInitialSettingError

                link_df.loc[pressure_valves, "initial_setting"] = self._converter.to_si(
                    link_df.loc[pressure_valves, "initial_setting"].to_numpy(), field=wntr.epanet.HydParam.Pressure
                )

                link_df.loc[fcvs, "initial_setting"] = self._converter.to_si(
                    link_df.loc[fcvs, "initial_setting"].to_numpy(), field=wntr.epanet.HydParam.Flow
                )

            if gpvs.any():
                if "headloss_curve" not in link_df:
                    raise GpvMissingCurveError

                link_df.loc[gpvs, "headloss_curve_name"] = self.curves.add_headloss(link_df.loc[gpvs, "headloss_curve"])

                if link_df.loc[gpvs, "headloss_curve_name"].hasnans:
                    raise GpvMissingCurveError

        pumps = link_df["link_type"] == "Pump"

        if pumps.any():
            try:
                link_df.loc[pumps, Field.PUMP_TYPE.value] = link_df.loc[pumps, Field.PUMP_TYPE.value].str.upper()
            except (KeyError, AttributeError):
                raise PumpTypeError from None

            if not link_df.loc[pumps, Field.PUMP_TYPE.value].isin(PumpTypes._member_names_).all():
                raise PumpTypeError

            power_pumps = link_df[Field.PUMP_TYPE.value] == PumpTypes.POWER.name
            head_pumps = link_df[Field.PUMP_TYPE.value] == PumpTypes.HEAD.name

            if power_pumps.any():
                if Field.POWER.value not in link_df:
                    raise PumpPowerError
                if link_df.loc[power_pumps, Field.POWER.value].hasnans:
                    raise PumpPowerError
                if (link_df.loc[power_pumps, Field.POWER.value] <= 0).any():
                    raise PumpPowerError

            if head_pumps.any():
                if Field.PUMP_CURVE.value not in link_df:
                    raise PumpCurveMissingError

                link_df["pump_curve_name"] = self.curves.add_head(link_df[Field.PUMP_CURVE.value])

                if link_df.loc[head_pumps, "pump_curve_name"].hasnans:
                    raise PumpCurveMissingError

        if "speed_pattern" in link_df:
            link_df["speed_pattern_name"] = self.patterns.add_all(
                link_df.get("speed_pattern"), ModelLayer.PUMPS, Field.SPEED_PATTERN
            )

        if "energy_pattern" in link_df:
            link_df["energy_pattern"] = self.patterns.add_all(
                link_df.get("energy_pattern"), ModelLayer.PUMPS, Field.ENERGY_PATTERN
            )

        for layer in [ModelLayer.PIPES, ModelLayer.VALVES, ModelLayer.PUMPS]:
            layer_items = link_df["link_type"] == layer.field_type
            if layer_items.any():
                for field in layer.wq_fields():
                    if not field.field_group & FieldGroup.REQUIRED:
                        continue
                    if field.value not in link_df:
                        raise RequiredFieldError(layer, field)
                    if link_df.loc[layer_items, field.value].hasnans:
                        raise RequiredFieldError(layer, field)

        return link_df.drop(
            columns=["headloss_curve", "pump_curve", "speed_pattern"],
            errors="ignore",
        )

    def _check_for_duplicate_names(self, df: pd.DataFrame) -> None:
        """Check for duplicate 'name' entries in the dataframe.

        Args:
            df: DataFrame to check for duplicates.

        Raises:
            NetworkModelError: If duplicates are found.
        """
        if "name" in df.columns:
            duplicates = df.loc[df["name"].duplicated(), "name"]
            if not duplicates.empty:
                msg = tr("Duplicate names found: ") + ", ".join(duplicates.unique())
                raise NetworkModelError(msg)


@needs_wntr_pandas
def check_network(wn: wntr.network.WaterNetworkModel) -> None:
    """Checks for simple errors in the network that will otherwise not get good error messages from wntr/epanet

    This is a utility function. WNTR will already error on any of these problems, but the messages WNTR gives
    are not always so clear.

    Args:
        wn: WaterNetworkModel to check

    Raises:
        NetworkModelError: if any checks fail

    Example:
        >>> wn = wntr.network.WaterNetworkModel()
        >>> wn.add_junction("j1")
        >>> wn.add_junction("j2")
        >>> wn.add_pipe("p1", "j1", "j2")
        >>> check_network(wn)
        Traceback (most recent call last):
        ...
        wntrqgis.interface.NetworkModelError: At least one tank or reservoir is required

        >>> wn = wntr.network.WaterNetworkModel()
        >>> wn.add_junction("j1")
        >>> wn.add_junction("j2")
        >>> wn.add_tank("t1")
        >>> wn.add_pipe("p1", "j1", "j2")
        >>> check_network(wn)
        Traceback (most recent call last):
        ...
        wntrqgis.interface.NetworkModelError: the following nodes are not connected to any links: t1


    """
    if not wn.num_junctions:
        msg = tr("At least one junction is necessary")
        raise NetworkModelError(msg)

    if not wn.num_tanks and not wn.num_reservoirs:
        msg = tr("At least one tank or reservoir is required")
        raise NetworkModelError(msg)

    if not wn.num_links:
        msg = tr("At least one link (pipe, pump or valve) is necessary")
        raise NetworkModelError(msg)

    orphan_nodes = wn.nodes.unused()
    if len(orphan_nodes):
        msg = tr("the following nodes are not connected to any links: {orphan_node_list}").format(
            orphan_node_list=", ".join(orphan_nodes)
        )
        raise NetworkModelError(msg)


@needs_wntr_pandas
def _get_field_groups(wn: wntr.network.WaterNetworkModel):
    """Utility function for guessing what types of analysis a specific wn will undertake,
    and therefore which field types should be included."""

    field_groups = FieldGroup(0)
    if wn.options.quality.parameter.upper() != "NONE":  # intentional string 'none'
        field_groups = field_groups | FieldGroup.WATER_QUALITY_ANALYSIS
    if wn.options.report.energy != "NO":
        field_groups = field_groups | FieldGroup.ENERGY
    if wn.options.hydraulic.demand_model == "PDA":
        field_groups = field_groups | FieldGroup.PRESSURE_DEPENDENT_DEMAND

    return field_groups


class NetworkModelError(Exception):
    # def __init__(self, exception):
    #     super().__init__(f"error preparing model; {exception}")
    pass


class PatternError(NetworkModelError, ValueError):
    def __init__(self, pattern_string, layer: ModelLayer, pattern_type: Field):
        super().__init__(
            tr(
                "in {layer} problem reading {pattern_type}: {pattern_string} Patterns should be a string of numeric values separated by a space, or a list of numeric values."  # noqa: E501
            ).format(layer=layer.friendly_name, pattern_type=pattern_type.friendly_name, pattern_string=pattern_string)
        )


class CurveError(NetworkModelError, ValueError):
    def __init__(self, curve_string, curve_type: _Curves.Type):
        curve_name = ""
        if curve_type is _Curves.Type.HEAD:
            curve_name = tr("pump head")
        elif curve_type is _Curves.Type.EFFICIENCY:
            curve_name = tr("pump efficiency")
        elif curve_type is _Curves.Type.HEADLOSS:
            curve_name = tr("general purpose valve headloss")
        elif curve_type is _Curves.Type.VOLUME:
            curve_name = tr("tank volume")

        super().__init__(
            tr(
                'problem reading {curve_name} curve "{curve_string}". Curves should be of the form: (1, 2), (3.6, 4.7)'
            ).format(curve_name=curve_name, curve_string=curve_string)
        )


class WntrError(NetworkModelError):
    def __init__(self, exception):
        super().__init__(
            tr("error from WNTR. {exception_name}: {exception}").format(
                exception_name=type(exception).__name__, exception=exception
            )
        )


class UnitError(NetworkModelError, ValueError):
    def __init__(self, exception):
        super().__init__(
            tr("{exception} is not a known set of units. Possible units are: ").format(exception=exception)
            + ", ".join(FlowUnit._member_names_)
        )


class GenericRequiredFieldError(NetworkModelError):
    pass


class ValveError(NetworkModelError):
    pass


class ValveTypeError(ValveError, GenericRequiredFieldError):
    def __init__(self):
        super().__init__(
            tr(
                "Valve type ({valve_type}) must be set for all valves and must be one of the following values: {possible_values}"  # noqa: E501
            ).format(valve_type=Field.VALVE_TYPE.name.lower(), possible_values=", ".join(ValveType._member_names_))
        )


class GpvMissingCurveError(ValveError, GenericRequiredFieldError):
    def __init__(self):
        super().__init__(
            tr("{headloss_curve_name} ({headloss_curve}) must be set for all general purpose valves (GPV)").format(
                headloss_curve_name=Field.HEADLOSS_CURVE.friendly_name,
                headloss_curve=Field.HEADLOSS_CURVE.name.lower(),
            )
        )


class ValveInitialSettingError(ValveError, GenericRequiredFieldError):
    def __init__(self):
        super().__init__(
            tr(
                "{initial_setting_name} ({initial_setting}) must be set for all valves except general purpose valves"
            ).format(
                initial_setting_name=Field.INITIAL_SETTING.friendly_name,
                initial_setting=Field.INITIAL_SETTING.name.lower(),
            )
        )


class RequiredFieldError(GenericRequiredFieldError):
    """Raised when a required parameter is missing from the model."""

    def __init__(self, layer: ModelLayer, field: Field):
        super().__init__(
            tr("In {layer_type}, all elements must have {field_name} '{field_id}'").format(
                layer_type=layer.friendly_name, field_name=field.friendly_name, field_id=field.name.lower()
            )
        )


class PumpError(NetworkModelError):
    pass


class PumpTypeError(PumpError, GenericRequiredFieldError):
    def __init__(self):
        super().__init__(
            tr(
                "Pump type ({pump_type}) must be set for all pumps and must be one of the following values: {possible_values}"  # noqa: E501
            ).format(pump_type=Field.PUMP_TYPE.name.lower(), possible_values=", ".join(PumpTypes._member_names_))
        )


class PumpCurveMissingError(PumpError, GenericRequiredFieldError):
    def __init__(self):
        super().__init__(
            tr("{pump_curve_name} ({pump_curve}) must be set for all pumps of type HEAD").format(
                pump_curve_name=Field.PUMP_CURVE.friendly_name, pump_curve=Field.PUMP_CURVE.name.lower()
            )
        )


class PumpPowerError(PumpError, GenericRequiredFieldError):
    def __init__(self):
        super().__init__(
            tr("{pump_power_name} ({pump_power}) must be set for all pumps of type POWER").format(
                pump_power_name=Field.POWER.friendly_name, pump_power=Field.POWER.name.lower()
            )
        )
