# derived from running wntr.network.io.valid_gis_names(True)
import ast

import shapely
import wntr
from qgis.core import QgsFeature, QgsFeatureSink, QgsFields, QgsGeometry
from wntr.epanet.util import HydParam, QualParam

from wntrqgis.utilswithoutwntr import WqInField, WqInLayer


class WqWntrUtils:
    @staticmethod
    def get_wntr_conversion_param(field, layer):
        match field:
            case WqInField.ELEVATION:
                return HydParam.Elevation
            case WqInField.BASE_DEMAND:
                return HydParam.Demand
            case WqInField.EMITTER_COEFFICIENT:
                return HydParam.EmitterCoeff
            case WqInField.INITIAL_QUALITY:
                return QualParam.Quality
            case WqInField.MINIMUM_PRESSURE, WqInField.REQUIRED_PRESSURE:
                return HydParam.Pressure
            case WqInField.INIT_LEVEL, WqInField.MIN_LEVEL, WqInField.MAX_LEVEL, WqInField.BASE_HEAD:
                return HydParam.HydraulicHead
            case WqInField.DIAMETER:
                if layer is WqInLayer.TANKS:
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
        return None

    @staticmethod
    def result_gdfs_to_sink(result_gdfs, fields: QgsFields, item_geoms, sink: QgsFeatureSink):
        g = QgsGeometry()
        for name, geom in item_geoms.items():
            f = QgsFeature()
            g.fromWkb(shapely.to_wkb(geom))
            f.setGeometry(g)
            atts = [result_gdfs[field.value][name].to_list() for field in fields]
            f.setAttributes([name, *atts])
            sink.addFeature(f, QgsFeatureSink.FastInsert)

    @staticmethod
    def input_gdf_to_sink(gdf, fields: QgsFields, sink: QgsFeatureSink):
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

    @staticmethod
    def patterns_curves_from_df(dfs, wn, flow_units):
        next_pattern_name = 2  # first pattern must be '2' as default pattern in wntr is '1'
        next_curve_name = 1

        def _add_curve(curve_string, curve_type):
            if curve_string:
                nonlocal next_curve_name
                name = str(next_curve_name)
                curve_points = ast.literal_eval(curve_string)
                curve_points = WqWntrUtils._convert_curve_points(
                    curve_points, curve_type, flow_units, wntr.epanet.util.to_si
                )
                wn.add_curve(name=name, curve_type=curve_type, xy_tuples_list=curve_points)
                next_curve_name += 1
                return name
            return None

        def _add_pattern(pattern):
            if not pattern:
                return None
            if isinstance(pattern, str) and pattern != "":
                patternlist = ast.literal_eval(pattern)
            elif isinstance(pattern, list):
                patternlist = pattern
            nonlocal next_pattern_name
            name = str(next_pattern_name)
            wn.add_pattern(name=name, pattern=patternlist)
            next_pattern_name += 1
            return name

        for lyr, df in dfs.items():
            match lyr:
                case WqInLayer.JUNCTIONS:
                    if "demand_pattern" in df:
                        df["demand_pattern_name"] = df["demand_pattern"].apply(_add_pattern)

                case WqInLayer.RESERVOIRS:
                    if "head_pattern" in df:
                        df["head_pattern_name"] = df["head_pattern"].apply(_add_pattern)

                case WqInLayer.TANKS:
                    if "vol_curve" in df:
                        df["vol_curve_name"] = df["vol_curve"].apply(_add_curve, curve_type="VOLUME")

                case WqInLayer.PUMPS:
                    if "pump_curve" in df:
                        df["pump_curve_name"] = df["pump_curve"].apply(_add_curve, curve_type="HEAD")
                    if "speed_pattern" in df:
                        df["speed_pattern_name"] = df["speed_pattern"].apply(_add_pattern)
                    if "energy_pattern" in df:
                        # energy pattern does not use 'name'
                        df["energy_pattern"] = df["energy_pattern"].apply(_add_pattern)

    @staticmethod
    def pattern_curves_to_dfs(dfs, wn, flow_units):
        curves = {}
        for curve_name in list(wn.curve_name_list):
            curve = wn.get_curve(curve_name)
            curves[curve_name] = WqWntrUtils._convert_curve_points(
                curve.points, curve.curve_type, flow_units, wntr.epanet.util.from_si
            )

        def _pattern_string(pn):
            return "[" + ", ".join(map(str, wn.get_pattern(pn).multipliers)) + "]" if wn.get_pattern(pn) else None

        for lyr, df in dfs.items():
            match lyr:
                case WqInLayer.JUNCTIONS:
                    # Secial case for demands
                    df["base_demand"] = wn.query_node_attribute("base_demand", node_type=wntr.network.model.Junction)
                    df["demand_pattern"] = wn.query_node_attribute(
                        "demand_timeseries_list", node_type=wntr.network.model.Junction
                    ).apply(
                        lambda dtl: ("[" + ", ".join(map(str, dtl.pattern_list()[0].multipliers)) + "]")
                        if dtl.pattern_list() and dtl.pattern_list()[0]
                        else None
                    )
                case WqInLayer.RESERVOIRS:
                    if "head_pattern_name" in df:
                        df["head_pattern"] = df["head_pattern_name"].apply(_pattern_string)
                case WqInLayer.TANKS:
                    if "vol_curve_name" in df:
                        df["vol_curve"] = df["vol_curve_name"].apply(
                            lambda cn: repr(curves[cn]) if curves[cn] else None
                        )
                case WqInLayer.PUMPS:
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

    @staticmethod
    def _convert_curve_points(points, curve_type, flow_units, conversion_function):
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

    @staticmethod
    def add_demands_to_wntr(junctiondf, wn):
        """Special method only for WNTR 1.2.0 which doesn't do this automatically"""
        for junction_name, junction in wn.junctions():
            junction.demand_timeseries_list.clear()
            try:
                base_demand = junctiondf.at[junction_name, "base_demand"]
                pattern_name = junctiondf.at[junction_name, "demand_pattern_name"]
                if base_demand:
                    junction.add_demand(base=base_demand, pattern_name=pattern_name)
            except KeyError:
                pass

    @staticmethod
    def convert_dfs_from_si(dfs, flow_units, darcy_weisbach):
        WqWntrUtils._convert_dfs(dfs, flow_units, darcy_weisbach, wntr.epanet.util.from_si)

    @staticmethod
    def convert_dfs_to_si(dfs, flow_units, darcy_weisbach):
        WqWntrUtils._convert_dfs(dfs, flow_units, darcy_weisbach, wntr.epanet.util.to_si)

    @staticmethod
    def _convert_dfs(dfs, flow_units, darcy_weisbach, conversion_function):
        for layer, df in dfs.items():
            for fieldname, series in df.items():
                try:
                    conversion_param = WqWntrUtils.get_wntr_conversion_param(WqInField(fieldname), layer)
                except ValueError:
                    continue
                if not conversion_param:
                    continue
                df[fieldname] = series.apply(
                    WqWntrUtils._wntr_convert,
                    args=(conversion_function, flow_units, conversion_param, darcy_weisbach),
                    by_row=False,
                )

    @staticmethod
    def _wntr_convert(value, conversion_function, flow_units, conversion_param, darcy_weisbach):
        return conversion_function(
            flow_units,
            value,
            conversion_param,
            darcy_weisbach=darcy_weisbach,
        )
