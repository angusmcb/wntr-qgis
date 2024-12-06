from __future__ import annotations

import ast
import math
import warnings
from functools import partial
from typing import Any

import numpy as np
import pandas as pd
import wntr
from qgis.core import (
    NULL,
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsDistanceArea,
    QgsFeature,
    QgsFeatureSink,
    QgsFeatureSource,
    QgsFields,
    QgsGeometry,
    QgsPoint,
    QgsPointXY,
    QgsSpatialIndex,
    QgsUnitTypes,
)
from wntr.epanet.util import HydParam, QualParam

from wntrqgis.network_parts import (
    WqAnalysisType,
    WqCurve,
    WqElementFamily,
    WqField,
    WqFlowUnit,
    WqHeadlossFormula,
    WqLayer,
    WqModelField,
    WqModelLayer,
    WqResultField,
    WqResultLayer,
)

QGIS_VERSION_DISTANCE_UNIT_IN_QGIS = 33000

QGIS_DISTANCE_UNIT_METERS = (
    Qgis.DistanceUnit.Meters if Qgis.versionInt() >= QGIS_VERSION_DISTANCE_UNIT_IN_QGIS else QgsUnitTypes.DistanceMeters
)


class WqSimulationResults:
    """Process WNTR Simulation Results, outputing to QGIS feature sinks"""

    def __init__(self, wntr_simulation_results: wntr.sim.results.SimulationResults, unit_conversion: WqUnitConversion):
        self._unit_conversion = unit_conversion

        self._result_dfs = {}
        for lyr in WqResultLayer:
            gdfs = getattr(wntr_simulation_results, lyr.wntr_attr)
            for field in lyr.wq_fields:
                self._result_dfs[field] = gdfs[field.value]

    def to_sink(self, sink: QgsFeatureSink, fields: list[WqModelField], item_geoms):
        output_attributes = {}
        # test = {}
        for field in fields:
            converted_df = self._unit_conversion.whole_df_from_si(self._result_dfs[field], field)

            lists = converted_df.transpose().to_numpy().tolist()
            output_attributes[field.value] = pd.Series(lists, index=converted_df.columns)

            # test[field.value] = converted_df.squeeze()  # for single state analysis

        jointed_dataframe = pd.DataFrame(output_attributes, index=output_attributes[field.value].index)
        namesindex = jointed_dataframe.index
        jointed_dataframe.reset_index(inplace=True)
        jointed_dataframe.rename(columns={"index": "name"}, inplace=True)
        attribute_series = pd.Series(jointed_dataframe.to_numpy().tolist(), index=namesindex)

        attribute_and_geom = pd.DataFrame({"geometry": item_geoms, "attributes": attribute_series}, index=namesindex)

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


class WqUnitConversion:
    """Manages conversion to and from SI units"""

    def __init__(self, flow_units: WqFlowUnit, headloss_formula: WqHeadlossFormula):
        self._flow_units = wntr.epanet.util.FlowUnits[flow_units.name]
        self._darcy_weisbach = headloss_formula is WqHeadlossFormula.DARCY_WEISBACH

    def to_si(self, value, field: WqField, layer: WqLayer | None = None):
        if (not isinstance(value, (int, float))) or isinstance(value, bool):
            return value
        try:
            conversion_param = self._get_wntr_conversion_param(field, layer)
        except ValueError:
            return value
        return wntr.epanet.util.to_si(
            self._flow_units, value, param=conversion_param, darcy_weisbach=self._darcy_weisbach
        )

    def from_si(self, value, field: WqField, layer: WqLayer | None = None):
        if (not isinstance(value, (int, float))) or isinstance(value, bool):
            return value
        try:
            conversion_param = self._get_wntr_conversion_param(field, layer)
        except ValueError:
            return value

        return wntr.epanet.util.from_si(
            self._flow_units, value, param=conversion_param, darcy_weisbach=self._darcy_weisbach
        )

    def _get_wntr_conversion_param(self, field: WqField, layer: WqLayer | None = None) -> QualParam | HydParam:
        # match field:
        if field is WqModelField.ELEVATION:
            return HydParam.Elevation
        if field is WqModelField.BASE_DEMAND or field is WqResultField.DEMAND:
            return HydParam.Demand
        if field is WqModelField.EMITTER_COEFFICIENT:
            return HydParam.EmitterCoeff
        if field in [WqModelField.INITIAL_QUALITY, WqResultField.QUALITY]:
            return QualParam.Quality
        if field in [WqModelField.MINIMUM_PRESSURE, WqModelField.REQUIRED_PRESSURE, WqResultField.PRESSURE]:
            return HydParam.Pressure
        if field in [
            WqModelField.INIT_LEVEL,
            WqModelField.MIN_LEVEL,
            WqModelField.MAX_LEVEL,
            WqModelField.BASE_HEAD,
            WqResultField.HEAD,
        ]:
            return HydParam.HydraulicHead
        if field is WqModelField.DIAMETER and layer is WqModelLayer.TANKS:
            return HydParam.TankDiameter
        if field is WqModelField.DIAMETER:
            return HydParam.PipeDiameter
        if field is WqModelField.MIN_VOL:
            return HydParam.Volume
        if field is WqModelField.BULK_COEFF:
            return QualParam.BulkReactionCoeff
        if field is WqModelField.LENGTH:
            return HydParam.Length
        if field is WqModelField.ROUGHNESS:
            return HydParam.RoughnessCoeff
        if field is WqModelField.WALL_COEFF:
            return QualParam.WallReactionCoeff
        if field is WqModelField.POWER:
            return HydParam.Power
        if field is WqResultField.FLOWRATE:
            return HydParam.Flow
        if field is WqResultField.HEADLOSS:
            return HydParam.HeadLoss
        if field is WqResultField.VELOCITY:
            return HydParam.Velocity
        msg = f"no param found for {field}"
        raise ValueError(msg)

    def curve_points_to_si(self, points, curve_type):
        return self._convert_curve_points(points, curve_type, wntr.epanet.util.to_si)

    def curve_points_from_si(self, points, curve_type):
        return self._convert_curve_points(points, curve_type, wntr.epanet.util.from_si)

    def _convert_curve_points(self, points, curve_type: WqCurve, conversion_function):
        flow_units = self._flow_units
        converted_points = []
        # match curve_type:
        if curve_type is WqCurve.VOLUME:
            for point in points:
                x = conversion_function(flow_units, point[0], HydParam.Length)
                y = conversion_function(flow_units, point[1], HydParam.Volume)
                converted_points.append((x, y))
        elif curve_type is WqCurve.HEAD:
            for point in points:
                x = conversion_function(flow_units, point[0], HydParam.Flow)
                y = conversion_function(flow_units, point[1], HydParam.HydraulicHead)
                converted_points.append((x, y))
        elif curve_type is WqCurve.EFFICIENCY:
            for point in points:
                x = conversion_function(flow_units, point[0], HydParam.Flow)
                y = point[1]
                converted_points.append((x, y))
        elif curve_type is WqCurve.HEADLOSS:
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

    # def converter_from_si(self, field, layer=None):
    #     try:
    #         conversion_param = self._get_wntr_conversion_param(field, layer)
    #     except ValueError:
    #         return lambda v: v
    #     return partial(
    #         wntr.epanet.util.from_si,
    #         self._flow_units,
    #         param=conversion_param,
    #         darcy_weisbach=self._darcy_weisbach,
    #     )

    def whole_df_from_si(self, df: pd.DataFrame, field: WqField, layer: WqLayer | None = None):
        try:
            conversion_param = self._get_wntr_conversion_param(field, layer)
        except ValueError:
            return df
        return wntr.epanet.util.from_si(
            self._flow_units,
            df,
            param=conversion_param,
            darcy_weisbach=self._darcy_weisbach,
        )

    def convert_dfs_from_si(self, dfs: dict[WqLayer, pd.DataFrame]):
        for layer, df in dfs.items():
            for fieldname, series in df.items():
                try:
                    conversion_param = self._get_wntr_conversion_param(WqModelField[str(fieldname).upper()], layer)
                except KeyError:
                    continue
                except ValueError:
                    continue
                convertor = partial(
                    wntr.epanet.util.from_si,
                    self._flow_units,
                    param=conversion_param,
                    darcy_weisbach=self._darcy_weisbach,
                )
                df[fieldname] = series.apply(convertor)  # , by_row=False)


class WqNetworkModelError(Exception):
    pass


class _SpatialIndex:
    def __init__(self):
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

    def add_pattern_to_wn(self, pattern):
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


class _Curves:
    def __init__(self, wn: wntr.network.WaterNetworkModel, unit_conversion: WqUnitConversion) -> None:
        self._wn = wn
        self._next_curve_name = 1
        self._unit_conversion = unit_conversion

    def add_curve_to_wn(self, curve_string, curve_type: WqCurve):
        if not curve_string:
            return None

        name = str(self._next_curve_name)
        curve_points = ast.literal_eval(curve_string)
        curve_points = self._unit_conversion.curve_points_to_si(curve_points, curve_type)
        self._wn.add_curve(name=name, curve_type=curve_type.value, xy_tuples_list=curve_points)
        self._next_curve_name += 1
        return name


class WqNetworkToWntr:
    """Convert from QGIS feature sources / layers to a WNTR model"""

    def __init__(
        self,
        unit_conversion: WqUnitConversion,
        transform_context: QgsCoordinateTransformContext | None = None,
        ellipsoid: str | None = "EPSG:7030",
    ):
        self._transform_context = (
            transform_context if transform_context is not None else QgsCoordinateTransformContext()
        )
        self._ellipsoid = ellipsoid
        self.geom_dict: dict[WqElementFamily, dict[str, QgsGeometry]] = {
            WqElementFamily.LINK: {},
            WqElementFamily.NODE: {},
        }
        self._unit_conversion = unit_conversion
        self.crs = None

    @property
    def crs(self):
        return self._crs

    @crs.setter
    def crs(self, crs: QgsCoordinateReferenceSystem | None):
        self._crs = crs
        if crs:
            self._measurer = QgsDistanceArea()
            self._measurer.setSourceCrs(crs, self._transform_context)
            self._measurer.setEllipsoid(self._ellipsoid)

    def to_wntr(self, feature_sources: dict[WqModelLayer, QgsFeatureSource], wn: wntr.network.WaterNetworkModel):
        self._pipe_length_warnings: list[str] = []
        self._used_names: dict[WqElementFamily, set[str]] = {WqElementFamily.NODE: set(), WqElementFamily.LINK: set()}

        self.patterns = _Patterns(wn)
        self.curves = _Curves(wn, self._unit_conversion)
        spatial_index = _SpatialIndex()

        for model_layer in WqModelLayer:
            source = feature_sources.get(model_layer)
            if source is None:
                continue

            map_of_columns_to_fields = self._map_columns_to_fields(source, model_layer)

            required_fields = [f for f in model_layer.wq_fields() if WqAnalysisType.REQUIRED in f.analysis_type]

            if not self.crs:
                self.crs = source.sourceCrs()

            if source.sourceCrs() != self.crs:
                coordinate_transform = QgsCoordinateTransform(source.sourceCrs(), self.crs, self._transform_context)
            else:
                coordinate_transform = None

            # df = self._source_to_df(source, map_of_columns_to_fields)
            # for column in df.select_dtypes(include=[np.number]):
            #     df[column] = self._unit_conversion.to_si(df[column], column, model_layer)

            ft: QgsFeature
            for ft in source.getFeatures():
                atts = self._get_attributes_from_feature(map_of_columns_to_fields, ft)

                for f, v in atts.items():
                    atts[f] = self._unit_conversion.to_si(v, f, model_layer)

                element_name = self._get_element_name(atts.get(WqModelField.NAME), model_layer)

                # TODO:  should check existance of columns before checking on individual features
                for required_field in required_fields:
                    if atts.get(required_field) is None:
                        msg = (
                            f"in {model_layer.friendly_name} the feature '{element_name}' "
                            f"must have a value for '{required_field.name.lower()}'"
                        )
                        raise WqNetworkModelError(msg)

                geometry: QgsGeometry = ft.geometry()

                if geometry.isNull():
                    msg = f"in {model_layer.friendly_name} the feature {element_name} has no geometry"
                    raise WqNetworkModelError(msg)

                if coordinate_transform:
                    geometry.transform(coordinate_transform)

                if model_layer.element_family is WqElementFamily.NODE:
                    spatial_index.add_node_to_spatial_index(geometry, element_name)

                    # geometry = self._get_3d_geometry(
                    #    geometry, atts.get(WqModelField.ELEVATION, atts.get(WqModelField.BASE_HEAD, 0))
                    # )
                else:
                    try:
                        geometry, start_node_name, end_node_name = spatial_index.snap_link_to_nodes(geometry)
                    except RuntimeError as e:
                        msg = f"in {model_layer.friendly_name} the feature {element_name}: {e} "
                        raise WqNetworkModelError(e) from None

                self.geom_dict[model_layer.element_family][element_name] = geometry

                try:
                    # match model_layer:
                    if model_layer is WqModelLayer.JUNCTIONS:
                        self._add_junction(wn, element_name, geometry, atts)
                    elif model_layer is WqModelLayer.TANKS:
                        self._add_tank(wn, element_name, geometry, atts)
                    elif model_layer is WqModelLayer.RESERVOIRS:
                        self._add_reservoir(wn, element_name, geometry, atts)
                    elif model_layer is WqModelLayer.PIPES:
                        self._add_pipe(wn, element_name, geometry, atts, start_node_name, end_node_name)
                    elif model_layer is WqModelLayer.PUMPS:
                        self._add_pump(wn, element_name, geometry, atts, start_node_name, end_node_name)
                    elif model_layer is WqModelLayer.VALVES:
                        self._add_valve(wn, element_name, geometry, atts, start_node_name, end_node_name)
                except (AssertionError, ValueError, RuntimeError) as e:
                    msg = f"in {model_layer.friendly_name} error when adding '{element_name}' to WNTR - {e}"
                    raise WqNetworkModelError(msg) from e

        self._output_pipe_length_warnings()
        self._wntr_network_error_check(wn)
        return wn

    def _source_to_df(self, source: QgsFeatureSource, map_of_columns_to_fields: list[WqModelField | str | None]):
        map_of_columns_to_fields = list(map_of_columns_to_fields)
        map_of_columns_to_fields.append("geometry")
        ftlist = []
        ft: QgsFeature
        for ft in source.getFeatures():
            attrs = [attr if attr != NULL else None for attr in ft]
            attrs.append(ft.geometry())
            ftlist.append(attrs)
        return pd.DataFrame(ftlist, columns=map_of_columns_to_fields)

    def _get_attributes_from_feature(self, map_of_columns_to_fields, feature):
        # slightly faster than zip
        atts = {}
        for i, field in enumerate(map_of_columns_to_fields):
            if field is not None:
                att = feature[i]
                if att is not None and att != NULL:
                    atts[field] = att
        return atts

    def _get_element_name(self, name_from_source: str | None, layer: WqModelLayer):
        if name_from_source:
            if name_from_source in self._used_names[layer.element_family]:
                msg = (
                    f"node name '{name_from_source}' is duplicated - "
                    "names must be unique across junctions, tanks and reservoirs"
                    if layer.element_family is WqElementFamily.NODE
                    else f"link name '{name_from_source}' is duplicated - "
                    "names must be unique across pipes, pumps and valves"
                )
                raise WqNetworkModelError(msg)
            feature_name = name_from_source
        else:
            i = 1
            while str(i) in self._used_names[layer.element_family]:
                i += 1
            feature_name = str(i)
        self._used_names[layer.element_family].add(feature_name)
        return feature_name

    def _map_columns_to_fields(self, feature_source: QgsFeatureSource, layer: WqModelLayer):
        shape_name_map = {wq_field.name[:10]: wq_field.name for wq_field in WqModelField}
        column_names = [
            shape_name_map[fname.upper()] if fname.upper() in shape_name_map else fname.upper()
            for fname in feature_source.fields().names()
        ]
        possible_column_names = {field.name for field in layer.wq_fields()}  # this creates a set not dict
        return [WqModelField[cname] if cname in possible_column_names else None for cname in column_names]

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
        self, wn: wntr.network.WaterNetworkModel, name: str, geometry: QgsGeometry, attributes: dict[WqModelField, Any]
    ):
        # Prefer adding nodes using 'add_...()' function as wntr does more error checking this way
        wn.add_junction(
            name,
            base_demand=attributes.get(WqModelField.BASE_DEMAND, 0),
            demand_pattern=self.patterns.add_pattern_to_wn(attributes.get(WqModelField.DEMAND_PATTERN)),
            elevation=attributes.get(WqModelField.ELEVATION, 0),
            coordinates=self._get_point_coordinates(geometry),
            # demand_category=category,  NOT IMPLEMENTED
        )
        n = wn.get_node(name)
        n.emitter_coeff = attributes.get(WqModelField.EMITTER_COEFFICIENT)
        n.initial_quality = attributes.get(WqModelField.INITIAL_QUALITY)
        n.minimum_pressure = attributes.get(WqModelField.MINIMUM_PRESSURE)
        n.pressure_exponent = attributes.get(WqModelField.PRESSURE_EXPONENT)
        n.required_pressure = attributes.get(WqModelField.REQUIRED_PRESSURE)

    def _add_tank(
        self, wn: wntr.network.WaterNetworkModel, name: str, geometry: QgsGeometry, attributes: dict[WqModelField, Any]
    ):
        wn.add_tank(
            name,
            elevation=attributes.get(WqModelField.ELEVATION, 0),
            init_level=attributes.get(WqModelField.INIT_LEVEL),  # REQUIRED
            min_level=attributes.get(WqModelField.MIN_LEVEL),  # REQUIRED
            max_level=attributes.get(WqModelField.MAX_LEVEL),  # REQUIRED
            diameter=attributes.get(WqModelField.DIAMETER, 0),
            min_vol=attributes.get(WqModelField.MIN_VOL, 0),
            vol_curve=self.curves.add_curve_to_wn(attributes.get(WqModelField.VOL_CURVE), WqCurve.VOLUME),
            overflow=attributes.get(WqModelField.OVERFLOW, False),
            coordinates=self._get_point_coordinates(geometry),
        )
        n = wn.get_node(name)
        n.mixing_fraction = attributes.get(WqModelField.MIXING_FRACTION)
        if attributes.get(WqModelField.MIXING_MODEL):
            n.mixing_model = attributes.get(WqModelField.MIXING_MODEL)  # WNTR BUG : doesn't accept 'none' value
        n.bulk_coeff = attributes.get(WqModelField.BULK_COEFF)

    def _add_reservoir(
        self, wn: wntr.network.WaterNetworkModel, name: str, geometry: QgsGeometry, attributes: dict[WqModelField, Any]
    ):
        wn.add_reservoir(
            name,
            base_head=attributes.get(WqModelField.BASE_HEAD, 0),
            head_pattern=self.patterns.add_pattern_to_wn(attributes.get(WqModelField.HEAD_PATTERN)),
            coordinates=self._get_point_coordinates(geometry),
        )

    def _add_pipe(
        self,
        wn: wntr.network.WaterNetworkModel,
        name: str,
        geometry: QgsGeometry,
        attributes: dict[WqModelField, Any],
        start_node_name: str,
        end_node_name: str,
    ):
        wn.add_pipe(
            name,
            start_node_name,
            end_node_name,
            length=self._get_pipe_length(attributes.get(WqModelField.LENGTH), geometry, name),
            diameter=attributes.get(WqModelField.DIAMETER),  # REQUIRED
            roughness=attributes.get(WqModelField.ROUGHNESS),  # REQUIRED
            minor_loss=attributes.get(WqModelField.MINOR_LOSS, 0.0),
            initial_status=attributes.get(WqModelField.INITIAL_STATUS, "OPEN"),
            check_valve=attributes.get(WqModelField.CHECK_VALVE, False) is True
            or str(attributes.get(WqModelField.CHECK_VALVE)).lower() == "true",
        )
        link = wn.get_link(name)
        link.bulk_coeff = attributes.get(WqModelField.BULK_COEFF)
        link.wall_coeff = attributes.get(WqModelField.WALL_COEFF)
        link.vertices = self._get_vertex_list(geometry)

    def _add_pump(
        self,
        wn: wntr.network.WaterNetworkModel,
        name: str,
        geometry: QgsGeometry,
        attributes: dict[WqModelField, Any],
        start_node_name: str,
        end_node_name: str,
    ):
        wn.add_pump(
            name,
            start_node_name,
            end_node_name,
            pump_type=attributes.get(WqModelField.PUMP_TYPE, ""),
            pump_parameter=attributes.get(WqModelField.POWER)  # TODO: ERROR MESSAGESF OR THIS ARE NOT CLEAR
            if str(attributes.get(WqModelField.PUMP_TYPE, "")).lower() == "power"
            else self.curves.add_curve_to_wn(attributes.get(WqModelField.PUMP_CURVE), WqCurve.HEAD),
            speed=attributes.get(WqModelField.BASE_SPEED, 1.0),
            pattern=self.patterns.add_pattern_to_wn(attributes.get(WqModelField.SPEED_PATTERN)),
            initial_status=attributes.get(WqModelField.INITIAL_STATUS, "OPEN"),
        )
        link = wn.get_link(name)
        link.efficiency = self.curves.add_curve_to_wn(attributes.get(WqModelField.EFFICIENCY), WqCurve.EFFICIENCY)
        link.energy_pattern = self.patterns.add_pattern_to_wn(attributes.get(WqModelField.ENERGY_PATTERN))
        link.energy_price = attributes.get(WqModelField.ENERGY_PRICE)
        link.initial_setting = attributes.get(WqModelField.INITIAL_SETTING)  # bug ???
        link.vertices = self._get_vertex_list(geometry)

    def _add_valve(
        self,
        wn: wntr.network.WaterNetworkModel,
        name: str,
        geometry: QgsGeometry,
        attributes: dict[WqModelField, Any],
        start_node_name: str,
        end_node_name: str,
    ):
        if str(attributes.get(WqModelField.VALVE_TYPE)).lower() == "gpv":
            initial_setting = self.curves.add_curve_to_wn(
                attributes.get(WqModelField.INITIAL_SETTING), WqCurve.HEADLOSS
            )
        else:
            initial_setting = attributes.get(WqModelField.INITIAL_SETTING, 0)
        wn.add_valve(
            name,
            start_node_name,
            end_node_name,
            diameter=attributes.get(WqModelField.DIAMETER),
            valve_type=attributes.get(WqModelField.VALVE_TYPE),
            minor_loss=attributes.get(WqModelField.MINOR_LOSS, 0.0),
            initial_setting=initial_setting,
            initial_status=attributes.get(WqModelField.INITIAL_STATUS, "OPEN"),
        )
        link = wn.get_link(name)
        link.vertices = self._get_vertex_list(geometry)

    def _wntr_network_error_check(self, wn) -> None:
        """Checks for errors in the network that will otherwise not get good error messages from wntr/epanet"""
        if not wn.num_junctions:
            msg = "At least one junction is necessary"
            raise WqNetworkModelError(msg)
        if not wn.num_tanks and not wn.num_reservoirs:
            msg = "At least one tank or reservoir is required"
            raise WqNetworkModelError(msg)
        if not wn.num_links:
            msg = "At least one link (pipe, pump or valve) is necessary"
            raise WqNetworkModelError(msg)
        orphan_nodes = wn.nodes.unused()
        if len(orphan_nodes):
            msg = "the following nodes are not connected to any links: " + ", ".join(orphan_nodes)
            raise WqNetworkModelError(msg)


class WqNetworkFromWntr:
    """Converts from a WNTR network, adding to qgis feature sinks"""

    def __init__(self, wn, unit_conversion: WqUnitConversion):
        self._unit_conversion = unit_conversion
        self._dfs: dict[WqLayer, pd.DataFrame] = {}
        self._create_gis(wn)
        # gdfs: dict[WqLayer, pd.DataFrame] = {lyr: getattr(wn_gis, lyr.wntr_attr) for lyr in WqModelLayer}

        self._get_pattern_from_wn(self._dfs, wn)

        analysis_types = WqAnalysisType.BASE
        for lyr in WqModelLayer:
            cols = list(self._dfs[lyr].loc[:, ~self._dfs[lyr].isna().all()].columns)
            for col in cols:
                try:
                    analysis_types = analysis_types | WqModelField(col).analysis_type
                except ValueError:
                    continue

        self.analysis_types = analysis_types

        self._unit_conversion.convert_dfs_from_si(self._dfs)

    def write_to_sinks(self, sinks):
        for lyr, (sink, fields) in sinks.items():
            if not self._dfs[lyr].shape[0]:
                continue

            self._input_gdf_to_sink(self._dfs[lyr], fields, sink)

    def _input_gdf_to_sink(self, df, fields: QgsFields, sink: QgsFeatureSink):
        df.reset_index(inplace=True)  # , names="name")
        df.rename(columns={"index": "name"}, inplace=True)
        for row in df.itertuples():
            f = QgsFeature()
            # g = QgsGeometry()
            # g.fromWkb(shapely.to_wkb(row.geometry))
            f.setGeometry(row.geometry)
            f.setFields(fields)
            for fieldname in fields.names():
                f[fieldname] = getattr(row, fieldname, None)
            sink.addFeature(f, QgsFeatureSink.FastInsert)

    def _get_pattern_from_wn(self, dfs, wn):
        curves = {}
        for curve_name in list(wn.curve_name_list):
            curve = wn.get_curve(curve_name)
            curves[curve_name] = self._unit_conversion.curve_points_from_si(curve.points, WqCurve(curve.curve_type))

        def _pattern_string(pn):
            return " ".join(map(str, wn.get_pattern(pn).multipliers)) if wn.get_pattern(pn) else None

        for lyr, df in dfs.items():
            # match lyr:
            if lyr is WqModelLayer.JUNCTIONS:
                # Secial case for demands
                df["base_demand"] = wn.query_node_attribute("base_demand", node_type=wntr.network.model.Junction)

                df["demand_pattern"] = wn.query_node_attribute(
                    "demand_timeseries_list", node_type=wntr.network.model.Junction
                ).apply(
                    lambda dtl: (" ".join(map(str, dtl.pattern_list()[0].multipliers)))
                    if dtl.pattern_list() and dtl.pattern_list()[0]
                    else None
                )
            elif lyr is WqModelLayer.RESERVOIRS:
                if "head_pattern_name" in df:
                    df["head_pattern"] = df["head_pattern_name"].apply(_pattern_string)
            elif lyr is WqModelLayer.TANKS:
                if "vol_curve_name" in df:
                    df["vol_curve"] = df["vol_curve_name"].apply(lambda cn: repr(curves[cn]) if curves[cn] else None)
            elif lyr is WqModelLayer.PUMPS:
                # not all pumps will have a pump curve (power pumps)!
                if "pump_curve_name" in df:
                    df["pump_curve"] = df["pump_curve_name"].apply(
                        lambda cn: repr(curves[cn]) if isinstance(cn, str) and curves[cn] else None
                    )
                if "speed_pattern_name" in df:
                    df["speed_pattern"] = df["speed_pattern_name"].apply(_pattern_string)
                # 'energy pattern' is not called energy pattern name!
                if "energy_pattern" in df:
                    df["energy_pattern"] = df["energy_pattern"].apply(_pattern_string)

    def _create_gis(self, wn) -> None:
        """
        Create GIS data from a water network model.

        This method is used by wntr.network.io.to_gis

        Note: patterns, curves, rules, controls, sources, and options are not
        saved to the GIS data

        Parameters
        ----------
        wn : WaterNetworkModel
            Water network model
        crs : str, optional
            Coordinate reference system, by default None
        pumps_as_points : bool, optional
            Represent pumps as points (True) or lines (False), by default False
        valves_as_points : bool, optional
            Represent valves as points (True) or lines (False), by default False
        """

        def _extract_geodataframe(df, valid_base_names=None):
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

        # Junctions
        df = df_nodes[df_nodes["node_type"] == "Junction"]
        self._dfs[WqModelLayer.JUNCTIONS] = _extract_geodataframe(df)  # , valid_base_names["junctions"])
        pd.set_option("display.max_columns", 7)

        # Tanks
        df = df_nodes[df_nodes["node_type"] == "Tank"]
        self._dfs[WqModelLayer.TANKS] = _extract_geodataframe(df)  # , valid_base_names["tanks"])

        # Reservoirs
        df = df_nodes[df_nodes["node_type"] == "Reservoir"]
        self._dfs[WqModelLayer.RESERVOIRS] = _extract_geodataframe(df)  # , valid_base_names["reservoirs"])

        # Pipes
        df = df_links[df_links["link_type"] == "Pipe"]
        self._dfs[WqModelLayer.PIPES] = _extract_geodataframe(df)  # , valid_base_names["pipes"])

        # Pumps
        df = df_links[df_links["link_type"] == "Pump"]
        self._dfs[WqModelLayer.PUMPS] = _extract_geodataframe(df)  # , valid_base_names["pumps"])

        # Valves
        df = df_links[df_links["link_type"] == "Valve"]
        self._dfs[WqModelLayer.VALVES] = _extract_geodataframe(df)  # , valid_base_names["valves"])
