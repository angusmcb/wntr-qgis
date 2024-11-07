from __future__ import annotations

import ast
import math
import warnings
from functools import partial
from typing import TYPE_CHECKING

import shapely
import wntr
from qgis.core import (
    Qgis,
    QgsCoordinateTransformContext,
    QgsDistanceArea,
    QgsFeature,
    QgsFeatureSink,
    QgsFields,
    QgsGeometry,
    QgsPoint,
    QgsPointXY,
    QgsSpatialIndex,
)
from qgis.PyQt.QtCore import QVariant
from wntr.epanet.util import HydParam, QualParam

from wntrqgis.network_parts import (
    WqAnalysisType,
    WqField,
    WqFlowUnit,
    WqHeadlossFormula,
    WqInField,
    WqLayer,
    WqModelLayer,
    WqOutField,
    WqOutLayer,
)

if TYPE_CHECKING:
    import pandas as pd


class WqSimulationResults:
    """Process WNTR Simulation Results, outputing to QGIS feature sinks"""

    def __init__(self, wntr_simulation_results: wntr.sim.results.SimulationResults, unit_conversion: WqUnitConversion):
        self._unit_conversion = unit_conversion

        self._result_dfs = {}
        for lyr in WqOutLayer:
            gdfs = getattr(wntr_simulation_results, lyr.wntr_attr)
            for field in lyr.wq_fields:
                self._result_dfs[field] = gdfs[field.value]

    def to_sink(self, sink: QgsFeatureSink, fields: list[WqInField], item_geoms):
        converted_dfs = {}

        for field in fields:
            # converted_dfs[field] = self._result_dfs[field].apply(self._unit_conversion.converter_from_si(field))
            converted_dfs[field] = self._unit_conversion.whole_df_from_si(self._result_dfs[field], field)
        for name, geom in item_geoms.items():
            f = QgsFeature()
            f.setGeometry(geom)
            atts = [converted_dfs[field][name].to_list() for field in fields]
            f.setAttributes([name, *atts])
            sink.addFeature(f, QgsFeatureSink.FastInsert)


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
        match field:
            case WqInField.ELEVATION:
                return HydParam.Elevation
            case WqInField.BASE_DEMAND | WqOutField.DEMAND:
                return HydParam.Demand
            case WqInField.EMITTER_COEFFICIENT:
                return HydParam.EmitterCoeff
            case WqInField.INITIAL_QUALITY | WqOutField.QUALITY:
                return QualParam.Quality
            case WqInField.MINIMUM_PRESSURE | WqInField.REQUIRED_PRESSURE | WqOutField.PRESSURE:
                return HydParam.Pressure
            case (
                WqInField.INIT_LEVEL
                | WqInField.MIN_LEVEL
                | WqInField.MAX_LEVEL
                | WqInField.BASE_HEAD
                | WqOutField.HEAD
            ):
                return HydParam.HydraulicHead
            case WqInField.DIAMETER:
                if layer is WqModelLayer.TANKS:
                    return HydParam.TankDiameter
                return HydParam.PipeDiameter
            case WqInField.MIN_VOL:
                return HydParam.Volume
            case WqInField.BULK_COEFF:
                return QualParam.BulkReactionCoeff
            case WqInField.LENGTH:
                return HydParam.Length
            case WqInField.ROUGHNESS:
                return HydParam.RoughnessCoeff
            case WqInField.WALL_COEFF:
                return QualParam.WallReactionCoeff
            case WqInField.POWER:
                return HydParam.Power
            case WqOutField.FLOWRATE:
                return HydParam.Flow
            case WqOutField.HEADLOSS:
                return HydParam.HeadLoss
            case WqOutField.VELOCITY:
                return HydParam.Velocity
        msg = f"no param found for {field}"
        raise ValueError(msg)

    def curve_points_to_si(self, points, curve_type):
        return self._convert_curve_points(points, curve_type, wntr.epanet.util.to_si)

    def curve_points_from_si(self, points, curve_type):
        return self._convert_curve_points(points, curve_type, wntr.epanet.util.from_si)

    def _convert_curve_points(self, points, curve_type: str, conversion_function):
        flow_units = self._flow_units
        converted_points = []
        match curve_type:
            case "VOLUME":
                for point in points:
                    x = conversion_function(flow_units, point[0], HydParam.Length)
                    y = conversion_function(flow_units, point[1], HydParam.Volume)
                    converted_points.append((x, y))
            case "HEAD":
                for point in points:
                    x = conversion_function(flow_units, point[0], HydParam.Flow)
                    y = conversion_function(flow_units, point[1], HydParam.HydraulicHead)
                    converted_points.append((x, y))
            case "EFFICIENCY":
                for point in points:
                    x = conversion_function(flow_units, point[0], HydParam.Flow)
                    y = point[1]
                    converted_points.append((x, y))
            case "HEADLOSS":
                for point in points:
                    x = conversion_function(flow_units, point[0], HydParam.Flow)
                    y = conversion_function(flow_units, point[1], HydParam.HeadLoss)
                    converted_points.append((x, y))
            case _:
                for point in points:
                    x = point[0]
                    y = point[1]
                    converted_points.append((x, y))
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
                    conversion_param = self._get_wntr_conversion_param(WqInField(fieldname), layer)
                except ValueError:
                    continue
                convertor = partial(
                    wntr.epanet.util.from_si,
                    self._flow_units,
                    param=conversion_param,
                    darcy_weisbach=self._darcy_weisbach,
                )
                df[fieldname] = series.apply(convertor, by_row=False)


class WqNetworkModelError(Exception):
    pass


class WqNetworkToWntr:
    """Interface between QGIS sources and WNTR models"""

    def __init__(
        self,
        unit_conversion: WqUnitConversion,
        transform_context: QgsCoordinateTransformContext | None = None,
        ellipsoid: str | None = None,
    ):
        self._transform_context = (
            transform_context if transform_context is not None else QgsCoordinateTransformContext()
        )
        self._ellipsoid = ellipsoid
        self.geom_dict: dict[WqOutLayer, dict[str, QgsGeometry]] = {WqOutLayer.LINKS: {}, WqOutLayer.NODES: {}}
        self._unit_conversion = unit_conversion

    def to_wntr(self, sources, wn):
        self._node_spatial_index = QgsSpatialIndex()
        self._nodelist = []
        self._next_pattern_name = 2
        self._next_curve_name = 1
        pipe_length_warnings = []
        nodenames = set()
        linknames = set()
        shape_name_map = {wq_field.value[:10]: wq_field.value for wq_field in WqInField}

        for in_layer in WqModelLayer:
            source = sources.get(WqModelLayer(in_layer))  # Can either be string or enum
            if source is None:
                continue

            column_names = [
                shape_name_map[fname] if fname in shape_name_map else fname for fname in source.fields().names()
            ]
            possible_cnames = {field.value for field in in_layer.wq_fields()}  # this creates a set not dict
            column_fields = [WqInField(cname) if cname in possible_cnames else None for cname in column_names]
            required_fields = [f for f in in_layer.wq_fields() if WqAnalysisType.REQUIRED in f.analysis_type]

            self.crs = source.sourceCrs()
            measurer = QgsDistanceArea()
            measurer.setSourceCrs(self.crs, self._transform_context)
            measurer.setEllipsoid(self._ellipsoid)

            for ft in source.getFeatures():
                geom = ft.geometry()
                # Remove QVariant types (they are null) !
                atts = {
                    k: v
                    for k, v in zip(column_fields, ft.attributes())
                    if k is not None and v is not None and not isinstance(v, QVariant)
                }

                for f, v in atts.items():
                    atts[f] = self._unit_conversion.to_si(v, f, in_layer)

                ftname = atts.get(WqInField.NAME)  # for convenience and in future may be automatically assigned
                if not ftname:
                    # this needs to be checked seperately from other required fields as error message is different
                    msg = f"in {in_layer.friendly_name}, all features must have a value for 'name'"
                    raise WqNetworkModelError(msg)

                # TODO:  should check existance of columns before checking on individual features
                for required_field in required_fields:
                    if atts.get(required_field) is None:
                        msg = (
                            f"in {in_layer.friendly_name} the feature '{ftname}' "
                            f"must have a value for '{required_field.value}'"
                        )
                        raise WqNetworkModelError(msg)

                if geom.isNull():
                    msg = f"in {in_layer.friendly_name} the feature {ftname} has no geometry"
                    raise WqNetworkModelError(msg)

                if in_layer.is_node:
                    if ftname in nodenames:
                        msg = (
                            f"node name '{ftname}' is duplicated - "
                            "names must be unique across junctions, tanks and reservoirs"
                        )
                        raise WqNetworkModelError(msg)
                    nodenames.add(ftname)

                    ft.setId(len(self._nodelist))
                    self._nodelist.append(ft)
                    self._node_spatial_index.addFeature(ft)
                    self.geom_dict[WqOutLayer.NODES][ftname] = geom
                    p = geom.asPoint()
                    coordinates = [p.x(), p.y()]
                else:
                    if ftname in linknames:
                        msg = (
                            f"link name '{ftname}' is duplicated - names must be unique across pipes, pumps and valves"
                        )
                        raise WqNetworkModelError(msg)
                    linknames.add(ftname)

                    vertices = list(geom.vertices())
                    start_point = vertices.pop(0)
                    end_point = vertices.pop()
                    vertex_list = [(v.x(), v.y()) for v in vertices]
                    original_length = measurer.measureLength(geom)
                    try:
                        (new_start_point, start_node_name) = self._snapper(start_point, measurer, original_length)
                        (new_end_point, end_node_name) = self._snapper(end_point, measurer, original_length)
                    except RuntimeError as e:
                        msg = f"in {in_layer.friendly_name} the feature {ftname} couldn't snap: {e}"
                        raise WqNetworkModelError(msg) from None

                    if start_node_name == end_node_name:
                        msg = (
                            f"in {in_layer.friendly_name} the feature {ftname} "
                            f"connects to the same node on both ends ({start_node_name})"
                        )
                        raise WqNetworkModelError(msg)

                    newgeom = QgsGeometry.fromPolyline([new_start_point, *vertices, new_end_point])
                    self.geom_dict[WqOutLayer.LINKS][ftname] = newgeom
                    length = measurer.measureLength(newgeom)

                    if in_layer is WqModelLayer.PIPES and not math.isclose(
                        atts[WqInField.LENGTH], length, rel_tol=0.05, abs_tol=10
                    ):
                        # warnings are raised in bulk later, as very slow otherwise
                        pipe_length_warnings.append(ftname)

                    if measurer.lengthUnits() != Qgis.DistanceUnit.Meters:
                        # try:
                        length = measurer.convertLengthMeasurement(length, Qgis.DistanceUnit.Meters)
                        # msg = "length units not metres and cannot convert: " + str(measurer.lengthUnits())
                        # raise NotImplementedError(msg)
                try:
                    # Prefer adding nodes using 'add_...()' function as wntr does more error checking this way
                    match in_layer:
                        case WqModelLayer.JUNCTIONS:
                            wn.add_junction(
                                ftname,
                                base_demand=atts.get(WqInField.BASE_DEMAND, 0),
                                demand_pattern=self._add_pattern_to_wn(atts.get(WqInField.DEMAND_PATTERN), wn),
                                elevation=atts.get(WqInField.ELEVATION, 0),
                                coordinates=coordinates,
                                # demand_category=category,  NOT IMPLEMENTED
                            )
                            n = wn.get_node(ftname)
                            n.emitter_coeff = atts.get(WqInField.EMITTER_COEFFICIENT)
                            n.initial_quality = atts.get(WqInField.INITIAL_QUALITY)
                            n.minimum_pressure = atts.get(WqInField.MINIMUM_PRESSURE)
                            n.pressure_exponent = atts.get(WqInField.PRESSURE_EXPONENT)
                            n.required_pressure = atts.get(WqInField.REQUIRED_PRESSURE)
                        case WqModelLayer.TANKS:
                            wn.add_tank(
                                ftname,
                                elevation=atts.get(WqInField.ELEVATION, 0),
                                init_level=atts.get(WqInField.INIT_LEVEL),  # REQUIRED
                                min_level=atts.get(WqInField.MIN_LEVEL),  # REQUIRED
                                max_level=atts.get(WqInField.MAX_LEVEL),  # REQUIRED
                                diameter=atts.get(WqInField.DIAMETER, 0),
                                min_vol=atts.get(WqInField.MIN_VOL, 0),
                                vol_curve=self._add_curve_to_wn(atts.get(WqInField.VOL_CURVE), "VOLUME", wn),
                                overflow=atts.get(WqInField.OVERFLOW, False),
                                coordinates=coordinates,
                            )
                            n = wn.get_node(ftname)
                            n.mixing_fraction = atts.get(WqInField.MIXING_FRACTION)
                            if atts.get(WqInField.MIXING_MODEL):
                                n.mixing_model = atts.get(
                                    WqInField.MIXING_MODEL
                                )  # WNTR BUG : doesn't accept 'none' value
                            n.bulk_coeff = atts.get(WqInField.BULK_COEFF)
                        case WqModelLayer.RESERVOIRS:
                            wn.add_reservoir(
                                ftname,
                                base_head=atts.get(WqInField.BASE_HEAD, 0),
                                head_pattern=self._add_pattern_to_wn(atts.get(WqInField.HEAD_PATTERN), wn),
                                coordinates=coordinates,
                            )
                        case WqModelLayer.PIPES:
                            wn.add_pipe(
                                ftname,
                                start_node_name,
                                end_node_name,
                                length=atts.get(WqInField.LENGTH),  # REQUIRED
                                diameter=atts.get(WqInField.DIAMETER),  # REQUIRED
                                roughness=atts.get(WqInField.ROUGHNESS),  # REQUIRED
                                minor_loss=atts.get(WqInField.MINOR_LOSS, 0.0),
                                initial_status=atts.get(WqInField.INITIAL_STATUS, "OPEN"),
                                check_valve=atts.get(WqInField.CHECK_VALVE) is True
                                or str(atts.get(WqInField.CHECK_VALVE)).lower() == "true"
                                or False,
                            )
                            link = wn.get_link(ftname)
                            link.bulk_coeff = atts.get(WqInField.BULK_COEFF)
                            link.wall_coeff = atts.get(WqInField.WALL_COEFF)
                            link.vertices = vertex_list
                        case WqModelLayer.PUMPS:
                            wn.add_pump(
                                ftname,
                                start_node_name,
                                end_node_name,
                                pump_type=atts.get(WqInField.PUMP_TYPE, ""),
                                pump_parameter=atts.get(WqInField.POWER)  # TODO: ERROR MESSAGESF OR THIS ARE NOT CLEAR
                                if atts.get(WqInField.PUMP_TYPE, "").lower() == "power"
                                else self._add_curve_to_wn(atts.get(WqInField.PUMP_CURVE), "HEAD", wn),
                                speed=atts.get(WqInField.BASE_SPEED, 1.0),
                                pattern=self._add_pattern_to_wn(atts.get(WqInField.SPEED_PATTERN), wn),
                                initial_status=atts.get(WqInField.INITIAL_STATUS, "OPEN"),
                            )
                            link = wn.get_link(ftname)
                            link.efficiency = atts.get(WqInField.EFFICIENCY)
                            link.energy_pattern = self._add_pattern_to_wn(atts.get(WqInField.ENERGY_PATTERN), wn)
                            link.energy_price = atts.get(WqInField.ENERGY_PRICE)
                            link.initial_setting = atts.get(WqInField.INITIAL_SETTING)  # bug ???
                            link.vertices = vertex_list
                        case WqModelLayer.VALVES:
                            wn.add_valve(
                                ftname,
                                start_node_name,
                                end_node_name,
                                diameter=atts.get(WqInField.DIAMETER),
                                valve_type=atts.get(WqInField.VALVE_TYPE),
                                minor_loss=atts.get(WqInField.MINOR_LOSS, 0.0),
                                initial_setting=atts.get(WqInField.INITIAL_SETTING, 0),
                                initial_status=atts.get(WqInField.INITIAL_STATUS, "OPEN"),
                            )
                            link = wn.get_link(ftname)
                            if atts.get(WqInField.VALVE_TYPE).lower() == "gpv":
                                msg = "GPV headloss curves not implemented"
                                raise NotImplementedError(msg)
                                # link.headloss_curve_name = self._add_curve_to_wn(atts.get(WqInField.), "HEAD",wn)
                            link.vertices = vertex_list
                except (AssertionError, ValueError, RuntimeError) as e:
                    msg = f"in {in_layer.friendly_name} error when adding '{ftname}' to WNTR - {e}"
                    raise WqNetworkModelError(msg) from None

        if pipe_length_warnings:
            msg = (
                f"the following {len(pipe_length_warnings)} pipes had very differnt measured length vs attribute:"
                + ",".join(pipe_length_warnings)
            )
            warnings.warn(msg, stacklevel=1)

        self._wntr_network_error_check(wn)
        return wn

    def _wntr_network_error_check(self, wn) -> None:
        """Checks for errors in the network that will otherwise not get good error messages from wntr/epanet"""
        if not wn.num_junctions:
            msg = "At least one junction is necessary"
            raise WqNetworkModelError(msg)
        if not wn.num_tanks and not wn.num_reservoirs:
            msg = "At least one tank or reservoir is required"
            raise WqNetworkModelError(msg)
        if not wn.num_pipes and not wn.num_valves and not wn.num_pumps:
            msg = "At least one link (pipe, pump or valve) is necessary"
            raise WqNetworkModelError(msg)
        orphan_nodes = wn.nodes.unused()
        if len(orphan_nodes):
            msg = "the following nodes are not connected to any links: " + ", ".join(orphan_nodes)
            raise WqNetworkModelError(msg)

    def _snapper(self, line_vertex_point: QgsPoint, measurer: QgsDistanceArea, original_length: float):
        nearest = self._node_spatial_index.nearestNeighbor(QgsPointXY(line_vertex_point))
        new_start_point = self._nodelist[nearest[0]].geometry().asPoint()
        start_node_name = self._nodelist[nearest[0]].attribute("name")
        start_snap_distance = measurer.measureLine(new_start_point, QgsPointXY(line_vertex_point))
        if start_snap_distance > original_length * 0.1:
            msg = f"nearest node to snap to is too far ({start_node_name})"
            raise RuntimeError(msg)
        return (QgsPoint(new_start_point), start_node_name)

    def _add_pattern_to_wn(self, pattern, wn):
        if not pattern:
            return None
        if isinstance(pattern, str) and pattern != "":
            patternlist = ast.literal_eval(pattern)
        elif isinstance(pattern, list):
            patternlist = pattern

        name = str(self._next_pattern_name)
        wn.add_pattern(name=name, pattern=patternlist)
        self._next_pattern_name += 1
        return name

    def _add_curve_to_wn(self, curve_string, curve_type, wn):
        if not curve_string:
            return None

        name = str(self._next_curve_name)
        curve_points = ast.literal_eval(curve_string)
        curve_points = self._unit_conversion.curve_points_to_si(curve_points, curve_type)
        wn.add_curve(name=name, curve_type=curve_type, xy_tuples_list=curve_points)
        self._next_curve_name += 1
        return name


class WqNetworkFromWntr:
    def __init__(self, wn, unit_conversion: WqUnitConversion):
        self._unit_conversion = unit_conversion
        wn_gis = wntr.network.to_gis(wn)
        gdfs: dict[WqLayer, pd.DataFrame] = {lyr: getattr(wn_gis, lyr.wntr_attr) for lyr in WqModelLayer}

        self._get_pattern_from_wn(gdfs, wn)

        analysis_types = WqAnalysisType.BASE
        for lyr in WqModelLayer:
            cols = list(gdfs[lyr].loc[:, ~gdfs[lyr].isna().all()].columns)
            for col in cols:
                try:
                    analysis_types = analysis_types | WqInField(col).analysis_type
                except ValueError:
                    continue

        self.analysis_types = analysis_types

        self._unit_conversion.convert_dfs_from_si(gdfs)

        self._gdfs = gdfs

    def write_to_sinks(self, sinks):
        for lyr, (sink, fields) in sinks.items():
            if not self._gdfs[lyr].shape[0]:
                continue

            self._input_gdf_to_sink(self._gdfs[lyr], fields, sink)

    def _input_gdf_to_sink(self, gdf, fields: QgsFields, sink: QgsFeatureSink):
        gdf.reset_index(inplace=True, names="name")
        g = QgsGeometry()
        for row in gdf.itertuples():
            f = QgsFeature()
            g.fromWkb(shapely.to_wkb(row.geometry))
            f.setGeometry(g)
            f.setFields(fields)
            for fieldname in fields.names():
                f[fieldname] = getattr(row, fieldname, None)
            sink.addFeature(f, QgsFeatureSink.FastInsert)

    def _get_pattern_from_wn(self, dfs, wn):
        curves = {}
        for curve_name in list(wn.curve_name_list):
            curve = wn.get_curve(curve_name)
            curves[curve_name] = self._unit_conversion.curve_points_from_si(curve.points, curve.curve_type)

        def _pattern_string(pn):
            return "[" + ", ".join(map(str, wn.get_pattern(pn).multipliers)) + "]" if wn.get_pattern(pn) else None

        for lyr, df in dfs.items():
            match lyr:
                case WqModelLayer.JUNCTIONS:
                    # Secial case for demands
                    df["base_demand"] = wn.query_node_attribute("base_demand", node_type=wntr.network.model.Junction)
                    df["demand_pattern"] = wn.query_node_attribute(
                        "demand_timeseries_list", node_type=wntr.network.model.Junction
                    ).apply(
                        lambda dtl: ("[" + ", ".join(map(str, dtl.pattern_list()[0].multipliers)) + "]")
                        if dtl.pattern_list() and dtl.pattern_list()[0]
                        else None
                    )
                case WqModelLayer.RESERVOIRS:
                    if "head_pattern_name" in df:
                        df["head_pattern"] = df["head_pattern_name"].apply(_pattern_string)
                case WqModelLayer.TANKS:
                    if "vol_curve_name" in df:
                        df["vol_curve"] = df["vol_curve_name"].apply(
                            lambda cn: repr(curves[cn]) if curves[cn] else None
                        )
                case WqModelLayer.PUMPS:
                    # not all pumps will have a pump curve (power pumps)!
                    if "pump_curve_name" in df:
                        df["pump_curve"] = df["pump_curve_name"].apply(
                            lambda cn: repr(curves[cn])
                            if cn == cn and curves[cn]  #  noqa PLR0124 checking nan
                            else None
                        )
                    if "speed_pattern_name" in df:
                        df["speed_pattern"] = df["speed_pattern_name"].apply(_pattern_string)
                    # 'energy pattern' is not called energy pattern name!
                    if "energy_pattern" in df:
                        df["energy_pattern"] = df["energy_pattern"].apply(_pattern_string)
