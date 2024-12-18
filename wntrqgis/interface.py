"""
This module contains the interfaces for for converting between WNTR and QGIS, both model layers and simulation results.
"""

from __future__ import annotations

import ast
import math
import warnings
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pandas as pd
import wntr
from qgis.core import (
    NULL,
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsDistanceArea,
    QgsFeature,
    QgsFeatureRequest,
    QgsFeatureSink,
    QgsFeatureSource,
    QgsFields,
    QgsGeometry,
    QgsPoint,
    QgsPointXY,
    QgsProject,
    QgsSpatialIndex,
    QgsUnitTypes,
    QgsVectorLayer,  # noqa F401
)
from wntr.epanet.util import HydParam, QualParam

from wntrqgis.elements import (
    ElementFamily,
    FieldGroup,
    FlowUnit,
    HeadlossFormula,
    ModelField,
    ModelLayer,
    ResultField,
    ResultLayer,
)

if TYPE_CHECKING:
    from numpy.typing import ArrayLike

QGIS_VERSION_DISTANCE_UNIT_IN_QGIS = 33000

QGIS_DISTANCE_UNIT_METERS = (
    Qgis.DistanceUnit.Meters if Qgis.versionInt() >= QGIS_VERSION_DISTANCE_UNIT_IN_QGIS else QgsUnitTypes.DistanceMeters
)


class _UnitConversion:
    """Manages conversion to and from SI units

    Args:
        flow_units: The set of units which will be converted to/from (or SI units for no conversion)
        headloss_formula: Used to determine how to handle conversion of the roughness coefficient
    """

    def __init__(self, flow_units: FlowUnit | wntr.epanet.util.FlowUnits, headloss_formula: HeadlossFormula):
        if isinstance(flow_units, wntr.epanet.util.FlowUnits):
            self._flow_units = flow_units
        else:
            self._flow_units = wntr.epanet.util.FlowUnits[flow_units.name]

        self._darcy_weisbach = headloss_formula is HeadlossFormula.DARCY_WEISBACH

    def to_si(
        self,
        value: float | ArrayLike | dict,
        field: ModelField | ResultField,
        layer: ModelLayer | ResultLayer | None = None,
    ):
        if field.python_type not in [int, float] or field.python_type is bool:
            return value
        try:
            conversion_param = self._get_wntr_conversion_param(field, layer)
        except ValueError:
            return value
        return wntr.epanet.util.to_si(
            self._flow_units, value, param=conversion_param, darcy_weisbach=self._darcy_weisbach
        )

    def from_si(
        self,
        value: float | ArrayLike | dict,
        field: ModelField | ResultField,
        layer: ModelLayer | ResultLayer | None = None,
    ):
        if field.python_type not in [int, float] or field.python_type is bool:
            return value
        try:
            conversion_param = self._get_wntr_conversion_param(field, layer)
        except ValueError:
            return value

        return wntr.epanet.util.from_si(
            self._flow_units, value, param=conversion_param, darcy_weisbach=self._darcy_weisbach
        )

    def _get_wntr_conversion_param(
        self, field: ModelField | ResultField, layer: ModelLayer | ResultLayer | None = None
    ) -> QualParam | HydParam:
        # match field:
        if field is ModelField.ELEVATION:
            return HydParam.Elevation
        if field is ModelField.BASE_DEMAND or field is ResultField.DEMAND:
            return HydParam.Demand
        if field is ModelField.EMITTER_COEFFICIENT:
            return HydParam.EmitterCoeff
        if field in [ModelField.INITIAL_QUALITY, ResultField.QUALITY]:
            return QualParam.Quality
        if field in [ModelField.MINIMUM_PRESSURE, ModelField.REQUIRED_PRESSURE, ResultField.PRESSURE]:
            return HydParam.Pressure
        if field in [
            ModelField.INIT_LEVEL,
            ModelField.MIN_LEVEL,
            ModelField.MAX_LEVEL,
            ModelField.BASE_HEAD,
            ResultField.HEAD,
        ]:
            return HydParam.HydraulicHead
        if field is ModelField.DIAMETER and layer is ModelLayer.TANKS:
            return HydParam.TankDiameter
        if field is ModelField.DIAMETER:
            return HydParam.PipeDiameter
        if field is ModelField.MIN_VOL:
            return HydParam.Volume
        if field is ModelField.BULK_COEFF:
            return QualParam.BulkReactionCoeff
        if field is ModelField.LENGTH:
            return HydParam.Length
        if field is ModelField.ROUGHNESS:
            return HydParam.RoughnessCoeff
        if field is ModelField.WALL_COEFF:
            return QualParam.WallReactionCoeff
        if field is ModelField.POWER:
            return HydParam.Power
        if field is ResultField.FLOWRATE:
            return HydParam.Flow
        if field is ResultField.HEADLOSS:
            return HydParam.HeadLoss
        if field is ResultField.VELOCITY:
            return HydParam.Velocity
        msg = f"no param found for {field}"
        raise ValueError(msg)

    def curve_points_to_si(
        self, points: list[tuple[float, float]], curve_type: _CurveType
    ) -> list[tuple[float, float]]:
        return self._convert_curve_points(points, curve_type, wntr.epanet.util.to_si)

    def curve_points_from_si(
        self, points: list[tuple[float, float]], curve_type: _CurveType
    ) -> list[tuple[float, float]]:
        return self._convert_curve_points(points, curve_type, wntr.epanet.util.from_si)

    def _convert_curve_points(self, points, curve_type: _CurveType, conversion_function) -> list[tuple[float, float]]:
        flow_units = self._flow_units
        converted_points: list[tuple[float, float]] = []

        if curve_type is _CurveType.VOLUME:
            for point in points:
                x = conversion_function(flow_units, point[0], HydParam.Length)
                y = conversion_function(flow_units, point[1], HydParam.Volume)
                converted_points.append((x, y))
        elif curve_type is _CurveType.HEAD:
            for point in points:
                x = conversion_function(flow_units, point[0], HydParam.Flow)
                y = conversion_function(flow_units, point[1], HydParam.HydraulicHead)
                converted_points.append((x, y))
        elif curve_type is _CurveType.EFFICIENCY:
            for point in points:
                x = conversion_function(flow_units, point[0], HydParam.Flow)
                y = point[1]
                converted_points.append((x, y))
        elif curve_type is _CurveType.HEADLOSS:
            for point in points:
                x = conversion_function(flow_units, point[0], HydParam.Flow)
                y = conversion_function(flow_units, point[1], HydParam.HeadLoss)
                converted_points.append((x, y))
        else:
            raise KeyError
            # for point in points:
            #     x = point[0]
            #     y = point[1]
            #     converted_points.append((x, y))
        return converted_points


# def write(
#     wn: wntr.network.WaterNetworkModel,
#     results: wntr.sim.SimulationResults | None = None,
#     crs: QgsCoordinateReferenceSystem | None = None,
#     units: str | None = None,
#     layers: str | None = None,
#     fields: list | None = None,
#     filename: str | None = None,
# ) -> dict[str, QgsVectorLayer] | None:
#     """Write from WNTR network model to QGIS Layers"""
#     return None


class Writer:
    """Writes a WNTR water network model, and optionally simulation results, to QGIS layers / feature sinks.

    Args:
        wn: The WNTR water network model that we will write from
        results: The simulation results. Default is that there are no simulation results.
        units: The units that it should be written in values include 'LPS','GPM'.
            Default is to use the units within the WaterNetworkModel options
    """

    def __init__(
        self,
        wn: wntr.network.WaterNetworkModel,
        results: wntr.sim.SimulationResults | None = None,  # noqa ARG002
        units: str | None = None,
    ) -> None:
        flow_units = (
            wntr.epanet.FlowUnits[str(units)] if units else wntr.epanet.FlowUnits[wn.options.hydraulic.inpfile_units]
        )
        unit_conversion = _UnitConversion(flow_units, HeadlossFormula(wn.options.hydraulic.headloss))

        self._dfs = self._create_gis(wn)
        self._process_dfs(self._dfs, wn, unit_conversion)

        self._geometries = self._get_geometries(wn)

        field_group = self.field_groups
        self.fields = [str(field.value) for field in ModelField if field.field_group & field_group]

    def _get_geometries(self, wn: wntr.network.WaterNetworkModel) -> dict[ElementFamily, dict[str, QgsGeometry]]:
        """As the WNTR simulation resulst do not contain any geometry information it is necessary to load them

        This function loads the geometries from a WaterNetworkModel"""
        geometries: dict[ElementFamily, dict[str, QgsGeometry]] = {ElementFamily.NODE: {}, ElementFamily.LINK: {}}

        for name, node in wn.nodes():
            geometries[ElementFamily.NODE][name] = QgsGeometry(QgsPoint(*node.coordinates))

        for name, link in wn.links():
            point_list = []
            point_list.append(QgsPoint(*link.start_node.coordinates))
            point_list.extend(QgsPoint(*vertex) for vertex in link.vertices)
            point_list.append(QgsPoint(*link.end_node.coordinates))
            geometries[ElementFamily.LINK][name] = QgsGeometry.fromPolyline(point_list)

        return geometries

    @property
    def field_groups(self) -> FieldGroup:
        """The groups of field used in the model"""

        analysis_types = FieldGroup.BASE
        for lyr in ModelLayer:
            cols = list(self._dfs[lyr].loc[:, ~self._dfs[lyr].isna().all()].columns)
            for col in cols:
                try:
                    analysis_types = analysis_types | ModelField(col).field_group
                except ValueError:
                    continue
        return analysis_types

    def _get_fields(self, layer: ModelLayer) -> list[ModelField]:
        layer_fields = layer.wq_fields()

        return [ModelField(field) for field in self.fields if ModelField(field) in layer_fields]

    def get_qgsfields(self, layer: ModelLayer) -> QgsFields:
        """Get the set of QgsFields that will be written by 'write'.

        This set of fields will need to be used when creating any sink/layer
        which will be written to by write_to_sink

        Args:
            layer: 'JUNCTIONS','PIPES','LINKS' etc.
        """

        return QgsFields([field.qgs_field for field in self._get_fields(layer)])

    def new_write(self, layer: ModelLayer, sink: QgsFeatureSink) -> None:
        """Write a fields from a layer to a Qgis feature sink

        Args:
            layer: which layer should be written to the sink: 'JUNCTIONS','PIPES','LINKS' etc.
            sink: the sink to write to
        """
        fields = self._get_fields(layer)
        df = self._dfs[layer]
        df = df.rename(columns={field.value: field for field in fields})
        df[ModelField.NAME] = df.index

        existingcols: list[ModelField] = cast(list, df.columns)
        cols = list(set(fields) - set(existingcols))

        if len(cols) > 0:
            df[cols] = None

        attributes_df = df[fields]

        attribute_series = pd.Series(attributes_df.to_numpy().tolist(), index=attributes_df.index)

        for name, attributes in attribute_series.items():
            f = QgsFeature()
            f.setGeometry(self._geometries[layer.element_family][name])
            f.setAttributes(attributes)
            sink.addFeature(f, QgsFeatureSink.FastInsert)

    def write(self, layer: ModelLayer, sink: QgsFeatureSink) -> None:
        """Write a fields from a layer to a Qgis feature sink

        Args:
            layer: which layer should be written to the sink: 'JUNCTIONS','PIPES','LINKS' etc.
            sink: the sink to write to
        """
        fields = self.get_qgsfields(layer)
        df = self._dfs[layer]
        df.reset_index(inplace=True)  # , names="name")
        df.rename(columns={"index": "name"}, inplace=True)
        for row in df.itertuples():
            f = QgsFeature()
            f.setGeometry(row.geometry)
            f.setFields(fields)
            for fieldname in fields.names():
                f[fieldname] = getattr(row, fieldname, None)
            sink.addFeature(f, QgsFeatureSink.FastInsert)

    def _process_dfs(
        self, dfs: dict[ModelLayer, pd.DataFrame], wn: wntr.network.WaterNetworkModel, unit_conversion: _UnitConversion
    ) -> None:
        patterns = _Patterns(wn)
        curves = _Curves(wn, unit_conversion)

        for lyr, df in dfs.items():
            if lyr is ModelLayer.JUNCTIONS:
                # Secial case for demands
                df["base_demand"] = wn.query_node_attribute("base_demand", node_type=wntr.network.model.Junction)

                # 'demand_pattern' didn't exist on node prior to wntr 1.3.0 so we have to go searching:
                df["demand_pattern"] = wn.query_node_attribute(
                    "demand_timeseries_list", node_type=wntr.network.model.Junction
                ).apply(lambda dtl: patterns.get_pattern_string(dtl.pattern_list()[0]))

            elif lyr is ModelLayer.RESERVOIRS:
                if "head_pattern_name" in df:
                    df["head_pattern"] = df["head_pattern_name"].apply(patterns.get_pattern_string_from_name)

            elif lyr is ModelLayer.TANKS:
                if "vol_curve_name" in df:
                    df["vol_curve"] = df["vol_curve_name"].apply(curves.get_curve_string_from_name)

            elif lyr is ModelLayer.PUMPS:
                # not all pumps will have a pump curve (power pumps)!
                if "pump_curve_name" in df:
                    df["pump_curve"] = df["pump_curve_name"].apply(curves.get_curve_string_from_name)

                if "speed_pattern_name" in df:
                    df["speed_pattern"] = df["speed_pattern_name"].apply(patterns.get_pattern_string_from_name)
                # 'energy pattern' is not called energy pattern name!
                if "energy_pattern" in df:
                    df["energy_pattern"] = df["energy_pattern"].apply(patterns.get_pattern_string_from_name)

            for fieldname, series in df.items():
                try:
                    field = ModelField[str(fieldname).upper()]
                except KeyError:
                    continue
                df[fieldname] = unit_conversion.from_si(series, field, lyr)

    def _create_gis(self, wn) -> dict[ModelLayer, pd.DataFrame]:
        def _extract_dataframe(df, valid_base_names=None) -> pd.DataFrame:
            if valid_base_names is None:
                valid_base_names = []

            # Drop any column with all NaN, this removes excess attributes
            # Valid base attributes that have all None values are added back
            # at the end of this routine
            df = df.loc[:, ~df.isna().all()]

            if df.shape[0] == 0:
                return pd.DataFrame()

            if "node_type" in df.columns:
                geom = [QgsGeometry(QgsPoint(x, y)) for x, y in df["coordinates"]]
                del df["node_type"]
            elif "link_type" in df.columns:
                geom = []
                for link_name in df["name"]:
                    link = wn.get_link(link_name)
                    ls = []
                    x, y = link.start_node.coordinates
                    ls.append(QgsPoint(x, y))
                    for x, y in link.vertices:
                        ls.append(QgsPoint(x, y))
                    x, y = link.end_node.coordinates
                    ls.append(QgsPoint(x, y))
                    geom.append(QgsGeometry.fromPolyline(ls))
                del df["link_type"]

            # Drop column if not a str, float, int, or bool (or np.bool_)
            # This drops columns like coordinates, vertices
            # This could be extended to keep additional data type (list,
            # tuple, network elements like Patterns, Curves)
            # drop_cols = []
            # for col in df.columns:
            #     # Added np.bool_ to the following check
            #     # Returned by df.to_dict('records') for some network models
            #     if not isinstance(df.iloc[0][col], (str, float, int, bool, np.bool_)):
            #         drop_cols.append(col)

            drop_cols = [
                col for col in df.columns if not isinstance(df.iloc[0][col], (str, float, int, bool, np.bool_))
            ]
            df = df.drop(columns=drop_cols)

            # Add back in valid base attributes that had all None values
            cols = list(set(valid_base_names) - set(df.columns))
            cols.sort()
            if len(cols) > 0:
                df[cols] = None

            # Set index
            if len(df) > 0:
                df.set_index("name", inplace=True)

            df["geometry"] = geom

            return df

        # Convert the WaterNetworkModel to a dictionary
        wn_dict = wn.to_dict()
        # Create dataframes for node and link attributes
        df_nodes = pd.DataFrame(wn_dict["nodes"])
        df_links = pd.DataFrame(wn_dict["links"])

        # valid_base_names = wntr.gis.network.WaterNetworkGIS._valid_names(complete_list=False, truncate_names=None)

        dfs = {}

        df = df_nodes[df_nodes["node_type"] == "Junction"]
        dfs[ModelLayer.JUNCTIONS] = _extract_dataframe(df)

        df = df_nodes[df_nodes["node_type"] == "Tank"]
        dfs[ModelLayer.TANKS] = _extract_dataframe(df)

        df = df_nodes[df_nodes["node_type"] == "Reservoir"]
        dfs[ModelLayer.RESERVOIRS] = _extract_dataframe(df)

        df = df_links[df_links["link_type"] == "Pipe"]
        dfs[ModelLayer.PIPES] = _extract_dataframe(df)

        df = df_links[df_links["link_type"] == "Pump"]
        dfs[ModelLayer.PUMPS] = _extract_dataframe(df)

        df = df_links[df_links["link_type"] == "Valve"]
        dfs[ModelLayer.VALVES] = _extract_dataframe(df)

        return dfs


class _SpatialIndex:
    def __init__(self) -> None:
        self._node_spatial_index = QgsSpatialIndex()
        self._nodelist: list[tuple[QgsPointXY, str]] = []

    def add_node_to_spatial_index(self, geometry: QgsGeometry, element_name: str):
        point = geometry.constGet().clone()
        feature_id = len(self._nodelist)
        self._nodelist.append((point, element_name))
        self._node_spatial_index.addFeature(feature_id, point.boundingBox())

    def _snapper(self, line_vertex_point: QgsPoint, original_length: float):
        nearest = self._node_spatial_index.nearestNeighbor(QgsPointXY(line_vertex_point))
        matched_node_point, matched_node_name = self._nodelist[nearest[0]]
        snap_distance = matched_node_point.distance(line_vertex_point)
        if snap_distance > original_length * 0.1:
            msg = f"nearest node to snap to is too far ({matched_node_name})."
            # Line length:{original_length} Snap Distance: {snap_distance}"
            raise RuntimeError(msg)
        return (matched_node_point, matched_node_name)

    def snap_link_to_nodes(
        self,
        geometry: QgsGeometry,
    ):
        vertices = list(geometry.vertices())
        start_point = vertices.pop(0)
        end_point = vertices.pop()
        original_length = geometry.length()
        try:
            (new_start_point, start_node_name) = self._snapper(start_point, original_length)
            (new_end_point, end_node_name) = self._snapper(end_point, original_length)
        except RuntimeError as e:
            msg = f"couldn't snap: {e}"
            raise RuntimeError(msg) from None

        if start_node_name == end_node_name:
            msg = f"connects to the same node on both ends ({start_node_name})"
            raise RuntimeError(msg)

        snapped_geometry = QgsGeometry.fromPolyline([new_start_point, *vertices, new_end_point])

        return snapped_geometry, start_node_name, end_node_name


class _Patterns:
    def __init__(self, wn: wntr.network.model.WaterNetworkModel) -> None:
        self._next_pattern_name = 2
        self._existing_patterns: dict[tuple, str] = {}
        self._wn = wn

    def add_pattern_to_wn(self, pattern: str | list | None):
        if not pattern:
            return None
        if isinstance(pattern, str) and pattern != "":
            patternlist = [float(item) for item in pattern.split()]
        elif isinstance(pattern, list):
            patternlist = pattern

        pattern_tuple = tuple(patternlist)

        if existing_pattern_name := self._existing_patterns.get(pattern_tuple):
            return existing_pattern_name

        name = str(self._next_pattern_name)
        self._wn.add_pattern(name=name, pattern=patternlist)
        self._existing_patterns[pattern_tuple] = name
        self._next_pattern_name += 1
        return name

    def get_pattern_string_from_name(self, pattern_name: str | None) -> str | None:
        if not pattern_name:
            return None
        # Do we need ever try to get non existant patterns? For now that will error
        return self.get_pattern_string(self._wn.get_pattern(pattern_name))

    def get_pattern_string(self, pattern: wntr.network.elements.Pattern | None) -> str | None:
        if not pattern:
            return None
        return " ".join(map(str, pattern.multipliers))


class _CurveType(Enum):
    HEAD = "HEAD"
    EFFICIENCY = "EFFICIENCY"
    VOLUME = "VOLUME"
    HEADLOSS = "HEADLOSS"


class _Curves:
    def __init__(self, wn: wntr.network.WaterNetworkModel, unit_conversion: _UnitConversion) -> None:
        self._wn = wn
        self._next_curve_name = 1
        self._unit_conversion = unit_conversion

        self._converted_curves = self._read_existing_curves()  # curve 'cache'

    def add_curve_to_wn(self, curve_string, curve_type: _CurveType):
        if not curve_string:
            return None

        name = str(self._next_curve_name)
        curve_points = ast.literal_eval(curve_string)
        curve_points = self._unit_conversion.curve_points_to_si(curve_points, curve_type)
        self._wn.add_curve(name=name, curve_type=curve_type.value, xy_tuples_list=curve_points)
        self._next_curve_name += 1
        return name

    def _read_existing_curves(self) -> dict[str, list[tuple[float, float]]]:
        """Sets up a sort of 'cache' of converted curves so we don't have to repeat over and over"""
        curves = {}

        for name, curve in self._wn.curves():
            curves[name] = self._unit_conversion.curve_points_from_si(curve.points, _CurveType(curve.curve_type))
        return curves

    def get_curve_string_from_name(self, curve_name: str) -> str:
        return repr(self._converted_curves[curve_name])


def read(
    layers: dict[ModelLayer, QgsFeatureSource],
    wn: wntr.network.WaterNetworkModel,
    project: QgsProject | None = None,
    crs: QgsCoordinateReferenceSystem | None = None,
    units: str | None = None,
    # headloss_formula: str | None = None,
) -> None:
    """Read from layers to a water network model

    Args:
        layers: layers to read
        wn: the model that the layers will be read into
        project: QgsProject instance, if none will use the current QgsProject.instance()
        crs: all geometry will be transformed into this crs for adding to the water network model
        units: the flow units to use. If not set will defualt to units in the water network model.
        headloss_formula: the headloss formula to use. If not set will defualt to option in the water network model."""
    if not wn:
        wn = wntr.network.WaterNetworkModel()
    flow_units = (
        wntr.epanet.FlowUnits[str(units)] if units else wntr.epanet.FlowUnits[wn.options.hydraulic.inpfile_units]
    )
    headloss_formula_type = HeadlossFormula(wn.options.hydraulic.headloss)
    unit_conversion = _UnitConversion(flow_units, headloss_formula_type)

    reader = _Reader(unit_conversion, project)
    reader.crs = crs
    reader.add_features_to_network_model(layers, wn)

    # return wn


class _Reader:
    """Read from QGIS feature sources / layers to a WNTR model"""

    def __init__(
        self,
        unit_conversion: _UnitConversion,
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
        self._unit_conversion = unit_conversion
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

        self._pipe_length_warnings: list[str] = []
        self._used_names: dict[ElementFamily, set[str]] = {ElementFamily.NODE: set(), ElementFamily.LINK: set()}

        self.patterns = _Patterns(wn)
        self.curves = _Curves(wn, self._unit_conversion)
        spatial_index = _SpatialIndex()

        for model_layer in ModelLayer:
            source = feature_sources.get(model_layer)
            if source is None:
                continue

            map_of_columns_to_fields = self._map_columns_to_fields(source, model_layer)

            required_fields = [f for f in model_layer.wq_fields() if FieldGroup.REQUIRED in f.field_group]

            if not self.crs:
                self.crs = source.sourceCrs()

            feature_request = QgsFeatureRequest()
            if source.sourceCrs() != self.crs:
                feature_request = feature_request.setDestinationCrs(self.crs, self._transform_context)

            # df = self._source_to_df(source, map_of_columns_to_fields)
            # for column in df.select_dtypes(include=[np.number]):
            #     df[column] = self._unit_conversion.to_si(df[column], column, model_layer)

            for ft in source.getFeatures(feature_request):
                ft = cast(QgsFeature, ft)
                atts = self._get_attributes_from_feature(map_of_columns_to_fields, ft)

                for f, v in atts.items():
                    atts[f] = self._unit_conversion.to_si(v, f, model_layer)

                element_name = self._get_element_name(atts.get(ModelField.NAME), model_layer)

                # TODO:  should check existance of columns before checking on individual features
                for required_field in required_fields:
                    if atts.get(required_field) is None:
                        msg = (
                            f"in {model_layer.friendly_name} the feature '{element_name}' "
                            f"must have a value for '{required_field.name.lower()}'"
                        )
                        raise NetworkModelError(msg)

                geometry = ft.geometry()

                if geometry.isNull():
                    msg = f"in {model_layer.friendly_name} the feature {element_name} has no geometry"
                    raise NetworkModelError(msg)

                if model_layer.element_family is ElementFamily.NODE:
                    spatial_index.add_node_to_spatial_index(geometry, element_name)

                    # geometry = self._get_3d_geometry(
                    #    geometry, atts.get(WqModelField.ELEVATION, atts.get(WqModelField.BASE_HEAD, 0))
                    # )
                else:
                    try:
                        geometry, start_node_name, end_node_name = spatial_index.snap_link_to_nodes(geometry)
                    except RuntimeError as e:
                        msg = f"in {model_layer.friendly_name} the feature {element_name}: {e} "
                        raise NetworkModelError(e) from None

                try:
                    if model_layer is ModelLayer.JUNCTIONS:
                        self._add_junction(wn, element_name, geometry, atts)
                    elif model_layer is ModelLayer.TANKS:
                        self._add_tank(wn, element_name, geometry, atts)
                    elif model_layer is ModelLayer.RESERVOIRS:
                        self._add_reservoir(wn, element_name, geometry, atts)
                    elif model_layer is ModelLayer.PIPES:
                        self._add_pipe(wn, element_name, geometry, atts, start_node_name, end_node_name)
                    elif model_layer is ModelLayer.PUMPS:
                        self._add_pump(wn, element_name, geometry, atts, start_node_name, end_node_name)
                    elif model_layer is ModelLayer.VALVES:
                        self._add_valve(wn, element_name, geometry, atts, start_node_name, end_node_name)
                except (AssertionError, ValueError, RuntimeError) as e:
                    msg = f"in {model_layer.friendly_name} error when adding '{element_name}' to WNTR - {e}"
                    raise NetworkModelError(msg) from e

        self._output_pipe_length_warnings()

    def _source_to_df(self, source: QgsFeatureSource, map_of_columns_to_fields: list[ModelField | str | None]):
        map_of_columns_to_fields = list(map_of_columns_to_fields)
        map_of_columns_to_fields.append("geometry")
        ftlist = []
        ft: QgsFeature
        for ft in source.getFeatures():
            attrs = [attr if attr != NULL else None for attr in ft]
            attrs.append(ft.geometry())
            ftlist.append(attrs)
        return pd.DataFrame(ftlist, columns=map_of_columns_to_fields)

    def _get_attributes_from_feature(
        self, map_of_columns_to_fields: list[ModelField | None], feature: QgsFeature
    ) -> dict[ModelField, Any]:
        # slightly faster than zip
        atts = {}
        for i, field in enumerate(map_of_columns_to_fields):
            if field is not None:
                att = feature[i]
                if att is not None and att != NULL:
                    atts[field] = att
        return atts

    def _get_element_name(self, name_from_source: str | None, layer: ModelLayer) -> str:
        if name_from_source:
            if name_from_source in self._used_names[layer.element_family]:
                msg = (
                    f"node name '{name_from_source}' is duplicated - "
                    "names must be unique across junctions, tanks and reservoirs"
                    if layer.element_family is ElementFamily.NODE
                    else f"link name '{name_from_source}' is duplicated - "
                    "names must be unique across pipes, pumps and valves"
                )
                raise NetworkModelError(msg)
            feature_name = name_from_source
        else:
            i = 1
            while str(i) in self._used_names[layer.element_family]:
                i += 1
            feature_name = str(i)
        self._used_names[layer.element_family].add(feature_name)
        return feature_name

    def _map_columns_to_fields(self, feature_source: QgsFeatureSource, layer: ModelLayer):
        shape_name_map = {wq_field.name[:10]: wq_field.name for wq_field in ModelField}
        column_names = [
            shape_name_map[fname.upper()] if fname.upper() in shape_name_map else fname.upper()
            for fname in feature_source.fields().names()
        ]
        possible_column_names = {field.name for field in layer.wq_fields()}  # this creates a set not dict
        return [ModelField[cname] if cname in possible_column_names else None for cname in column_names]

    def _get_point_coordinates(self, geometry: QgsGeometry):
        point = geometry.constGet()
        return point.x(), point.y()

    def _get_3d_geometry(self, geometry: QgsGeometry, z):
        point = geometry.constGet()
        point_3d = QgsPoint(point.x(), point.y(), z)
        return QgsGeometry(point_3d)

    def _get_pipe_length(self, attribute_length: float | None, geometry: QgsGeometry, pipe_name: str):
        length = self._measurer.measureLength(geometry)

        if self._measurer.lengthUnits() != QGIS_DISTANCE_UNIT_METERS:
            length = self._measurer.convertLengthMeasurement(length, QGIS_DISTANCE_UNIT_METERS)

        if not attribute_length:
            return length

        if not math.isclose(attribute_length, length, rel_tol=0.05, abs_tol=10):
            # warnings are raised in bulk later, as very slow otherwise
            self._pipe_length_warnings.append(pipe_name)
        return attribute_length

    def _output_pipe_length_warnings(self):
        if self._pipe_length_warnings:
            msg = (
                f"the following {len(self._pipe_length_warnings)} pipes had very differnt measured length vs attribute:"
                + ",".join(self._pipe_length_warnings)
            )
            warnings.warn(msg, stacklevel=1)

    def _get_vertex_list(self, geometry: QgsGeometry):
        vertices = list(geometry.vertices())
        return [(v.x(), v.y()) for v in vertices[1:-1]]

    def _add_junction(
        self, wn: wntr.network.WaterNetworkModel, name: str, geometry: QgsGeometry, attributes: dict[ModelField, Any]
    ):
        # Prefer adding nodes using 'add_...()' function as wntr does more error checking this way
        wn.add_junction(
            name,
            base_demand=attributes.get(ModelField.BASE_DEMAND, 0),
            demand_pattern=self.patterns.add_pattern_to_wn(attributes.get(ModelField.DEMAND_PATTERN)),
            elevation=attributes.get(ModelField.ELEVATION, 0),
            coordinates=self._get_point_coordinates(geometry),
            # demand_category=category,  NOT IMPLEMENTED
        )
        n = wn.get_node(name)
        n.emitter_coeff = attributes.get(ModelField.EMITTER_COEFFICIENT)
        n.initial_quality = attributes.get(ModelField.INITIAL_QUALITY)
        n.minimum_pressure = attributes.get(ModelField.MINIMUM_PRESSURE)
        n.pressure_exponent = attributes.get(ModelField.PRESSURE_EXPONENT)
        n.required_pressure = attributes.get(ModelField.REQUIRED_PRESSURE)

    def _add_tank(
        self, wn: wntr.network.WaterNetworkModel, name: str, geometry: QgsGeometry, attributes: dict[ModelField, Any]
    ):
        wn.add_tank(
            name,
            elevation=attributes.get(ModelField.ELEVATION, 0),
            init_level=attributes.get(ModelField.INIT_LEVEL),  # REQUIRED
            min_level=attributes.get(ModelField.MIN_LEVEL),  # REQUIRED
            max_level=attributes.get(ModelField.MAX_LEVEL),  # REQUIRED
            diameter=attributes.get(ModelField.DIAMETER, 0),
            min_vol=attributes.get(ModelField.MIN_VOL, 0),
            vol_curve=self.curves.add_curve_to_wn(attributes.get(ModelField.VOL_CURVE), _CurveType.VOLUME),
            overflow=attributes.get(ModelField.OVERFLOW, False),
            coordinates=self._get_point_coordinates(geometry),
        )
        n = wn.get_node(name)
        n.initial_quality = attributes.get(ModelField.INITIAL_QUALITY)
        n.mixing_fraction = attributes.get(ModelField.MIXING_FRACTION)
        if attributes.get(ModelField.MIXING_MODEL):
            n.mixing_model = attributes.get(ModelField.MIXING_MODEL)  # WNTR BUG : doesn't accept 'none' value
        n.bulk_coeff = attributes.get(ModelField.BULK_COEFF)

    def _add_reservoir(
        self, wn: wntr.network.WaterNetworkModel, name: str, geometry: QgsGeometry, attributes: dict[ModelField, Any]
    ):
        wn.add_reservoir(
            name,
            base_head=attributes.get(ModelField.BASE_HEAD, 0),
            head_pattern=self.patterns.add_pattern_to_wn(attributes.get(ModelField.HEAD_PATTERN)),
            coordinates=self._get_point_coordinates(geometry),
        )
        n = wn.get_node(name)
        n.initial_quality = attributes.get(ModelField.INITIAL_QUALITY)

    def _add_pipe(
        self,
        wn: wntr.network.WaterNetworkModel,
        name: str,
        geometry: QgsGeometry,
        attributes: dict[ModelField, Any],
        start_node_name: str,
        end_node_name: str,
    ):
        wn.add_pipe(
            name,
            start_node_name,
            end_node_name,
            length=self._get_pipe_length(attributes.get(ModelField.LENGTH), geometry, name),
            diameter=attributes.get(ModelField.DIAMETER),  # REQUIRED
            roughness=attributes.get(ModelField.ROUGHNESS),  # REQUIRED
            minor_loss=attributes.get(ModelField.MINOR_LOSS, 0.0),
            initial_status=attributes.get(ModelField.INITIAL_STATUS, "OPEN"),
            check_valve=attributes.get(ModelField.CHECK_VALVE, False) is True
            or str(attributes.get(ModelField.CHECK_VALVE)).lower() == "true",
        )
        link = wn.get_link(name)
        link.bulk_coeff = attributes.get(ModelField.BULK_COEFF)
        link.wall_coeff = attributes.get(ModelField.WALL_COEFF)
        link.vertices = self._get_vertex_list(geometry)

    def _add_pump(
        self,
        wn: wntr.network.WaterNetworkModel,
        name: str,
        geometry: QgsGeometry,
        attributes: dict[ModelField, Any],
        start_node_name: str,
        end_node_name: str,
    ):
        wn.add_pump(
            name,
            start_node_name,
            end_node_name,
            pump_type=attributes.get(ModelField.PUMP_TYPE, ""),
            pump_parameter=attributes.get(ModelField.POWER)  # TODO: ERROR MESSAGESF OR THIS ARE NOT CLEAR
            if str(attributes.get(ModelField.PUMP_TYPE, "")).lower() == "power"
            else self.curves.add_curve_to_wn(attributes.get(ModelField.PUMP_CURVE), _CurveType.HEAD),
            speed=attributes.get(ModelField.BASE_SPEED, 1.0),
            pattern=self.patterns.add_pattern_to_wn(attributes.get(ModelField.SPEED_PATTERN)),
            initial_status=attributes.get(ModelField.INITIAL_STATUS, "OPEN"),
        )
        link = wn.get_link(name)
        link.efficiency = self.curves.add_curve_to_wn(attributes.get(ModelField.EFFICIENCY), _CurveType.EFFICIENCY)
        link.energy_pattern = self.patterns.add_pattern_to_wn(attributes.get(ModelField.ENERGY_PATTERN))
        link.energy_price = attributes.get(ModelField.ENERGY_PRICE)
        link.initial_setting = attributes.get(ModelField.INITIAL_SETTING)  # bug ???
        link.vertices = self._get_vertex_list(geometry)

    def _add_valve(
        self,
        wn: wntr.network.WaterNetworkModel,
        name: str,
        geometry: QgsGeometry,
        attributes: dict[ModelField, Any],
        start_node_name: str,
        end_node_name: str,
    ):
        if str(attributes.get(ModelField.VALVE_TYPE)).lower() == "gpv":
            initial_setting = self.curves.add_curve_to_wn(
                attributes.get(ModelField.INITIAL_SETTING), _CurveType.HEADLOSS
            )
        else:
            initial_setting = attributes.get(ModelField.INITIAL_SETTING, 0)
        wn.add_valve(
            name,
            start_node_name,
            end_node_name,
            diameter=attributes.get(ModelField.DIAMETER),
            valve_type=attributes.get(ModelField.VALVE_TYPE),
            minor_loss=attributes.get(ModelField.MINOR_LOSS, 0.0),
            initial_setting=initial_setting,
            initial_status=attributes.get(ModelField.INITIAL_STATUS, "OPEN"),
        )
        link = wn.get_link(name)
        link.vertices = self._get_vertex_list(geometry)


def check_network(wn: wntr.network.WaterNetworkModel) -> None:
    """Checks for simple errors in the network that will otherwise not get good error messages from wntr/epanet

    This is a utility function. WNTR will already error on any of these problems, but the messages WNTR gives
    are not always so clear.

    Args:
        wn: WaterNetworkModel to check

    Raises:
        NetworkModelError: if any checks fail
    """

    if not wn.num_junctions:
        msg = "At least one junction is necessary"
        raise NetworkModelError(msg)
    if not wn.num_tanks and not wn.num_reservoirs:
        msg = "At least one tank or reservoir is required"
        raise NetworkModelError(msg)
    if not wn.num_links:
        msg = "At least one link (pipe, pump or valve) is necessary"
        raise NetworkModelError(msg)
    orphan_nodes = wn.nodes.unused()
    if len(orphan_nodes):
        msg = "the following nodes are not connected to any links: " + ", ".join(orphan_nodes)
        raise NetworkModelError(msg)


class SimulationResults:
    """Process WNTR Simulation Results, outputing to QGIS feature sinks

    Args:
        results: simulation result's from wntr's simulation module
        unit_conversion: set of units to convert to
    """

    def __init__(
        self,
        wn: wntr.network.WaterNetworkModel,
        results: wntr.sim.SimulationResults,
        unit_conversion: _UnitConversion,
    ) -> None:
        self._unit_conversion = unit_conversion

        self._result_dfs = {}
        for lyr in ResultLayer:
            gdfs = getattr(results, lyr.wntr_attr)
            for field in lyr.wq_fields:
                self._result_dfs[field] = gdfs[field.value]

        self._geometries = self._get_geometries(wn)

    def _get_geometries(self, wn: wntr.network.WaterNetworkModel) -> dict[ElementFamily, dict[str, QgsGeometry]]:
        """As the WNTR simulation resulst do not contain any geometry information it is necessary to load them

        This function loads the geometries from a WaterNetworkModel"""
        geometries: dict[ElementFamily, dict[str, QgsGeometry]] = {ElementFamily.NODE: {}, ElementFamily.LINK: {}}

        for name, node in wn.nodes():
            geometries[ElementFamily.NODE][name] = QgsGeometry(QgsPoint(*node.coordinates))

        for name, link in wn.links():
            point_list = []
            point_list.append(QgsPoint(*link.start_node.coordinates))
            point_list.extend(QgsPoint(*vertex) for vertex in link.vertices)
            point_list.append(QgsPoint(*link.end_node.coordinates))
            geometries[ElementFamily.LINK][name] = QgsGeometry.fromPolyline(point_list)

        return geometries

    def get_qgsfields(self, layer: ResultLayer) -> QgsFields:
        """Get the set of QgsFields that will be written by 'write_to_sink'.

        This set of fields will need to be used when creating any sink/layer
        which will be written to by write_to_sink
        """
        fields = QgsFields()
        fields.append(ModelField.NAME.qgs_field)
        for f in layer.wq_fields:
            fields.append(f.qgs_field)
        return fields

    def write(self, layer: ResultLayer, sink: QgsFeatureSink) -> None:
        """Add results to a feature sink

        Args:
            sink: qgs sink (which could be a layer)  to write to
            fields: list of fields that should be written
            name_geometry_map: dictionary mapping item names to geometries
        """
        output_attributes = {}

        # test = {}
        for field in layer.wq_fields:
            converted_df = self._unit_conversion.from_si(self._result_dfs[field], field)

            lists = converted_df.transpose().to_numpy().tolist()
            output_attributes[field.value] = pd.Series(lists, index=converted_df.columns)

            # test[field.value] = converted_df.squeeze()  # for single state analysis

        jointed_dataframe = pd.DataFrame(output_attributes, index=output_attributes[field.value].index)
        namesindex = jointed_dataframe.index
        jointed_dataframe.reset_index(inplace=True)
        jointed_dataframe.rename(columns={"index": "name"}, inplace=True)
        attribute_series = pd.Series(jointed_dataframe.to_numpy().tolist(), index=namesindex)

        attribute_and_geom = pd.DataFrame(
            {"geometry": self._geometries[layer.element_family], "attributes": attribute_series}, index=namesindex
        )

        for item in attribute_and_geom.itertuples(False):
            f = QgsFeature()
            f.setGeometry(item.geometry)
            f.setAttributes(item.attributes)
            sink.addFeature(f, QgsFeatureSink.FastInsert)

        # for name, geom in item_geoms.items():
        #     f = QgsFeature()
        #     f.setGeometry(geom)
        #     atts = attribute_series.loc[name]
        #     f.setAttributes(atts)
        #     # sink.addFeature(f, QgsFeatureSink.FastInsert)

        # for name, geom in item_geoms.items():
        #     f = QgsFeature()
        #     f.setGeometry(geom)
        #     atts = [converted_dfs[field][name].to_list() for field in fields]
        #     f.setAttributes([name, *atts])
        #     sink.addFeature(f, QgsFeatureSink.FastInsert)


class NetworkModelError(Exception):
    pass
