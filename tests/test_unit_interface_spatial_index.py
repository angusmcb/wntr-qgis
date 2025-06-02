import pytest
from qgis.core import QgsGeometry, QgsPoint, QgsPointXY

from wntrqgis.interface import (
    _SpatialIndex,
)


def test_spatial_index_add_node():
    index = _SpatialIndex()
    geometry = QgsGeometry(QgsPoint(1, 1))
    index.add_node(geometry, "node1")
    assert len(index._nodelist) == 1


def test_spatial_index_snap_link():
    index = _SpatialIndex()
    geometry = QgsGeometry.fromPolyline([QgsPoint(1, 1), QgsPoint(2, 2)])
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    index.add_node(QgsGeometry(QgsPoint(2, 2)), "node2")
    snapped_geometry, start_node, end_node = index.snap_link(geometry)
    assert start_node == "node1"
    assert end_node == "node2"


def test_spatial_index_snap_link_nearby():
    index = _SpatialIndex()
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    index.add_node(QgsGeometry(QgsPoint(2, 2)), "node2")
    geometry = QgsGeometry.fromPolyline([QgsPoint(1.01, 1.01), QgsPoint(1.92, 1.92)])
    snapped_geometry, start_node, end_node = index.snap_link(geometry)
    assert start_node == "node1"
    assert end_node == "node2"
    assert snapped_geometry.asPolyline() == [QgsPointXY(1, 1), QgsPointXY(2, 2)]


def test_spatial_index_snap_link_far_apart():
    index = _SpatialIndex()
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    index.add_node(QgsGeometry(QgsPoint(2, 2)), "node2")
    geometry = QgsGeometry.fromPolyline([QgsPoint(10, 10), QgsPoint(20, 20)])
    with pytest.raises(RuntimeError, match=r"nearest node to snap to is too far \(node2\)"):
        index.snap_link(geometry)


def test_spatial_index_snap_link_same_node():
    index = _SpatialIndex()
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    geometry = QgsGeometry.fromPolyline([QgsPoint(1.01, 1.01), QgsPoint(2, 3), QgsPoint(1.02, 1.02)])
    with pytest.raises(RuntimeError, match="connects to the same node on both ends"):
        index.snap_link(geometry)


def test_spatial_index_snap_link_multi_part():
    index = _SpatialIndex()
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    index.add_node(QgsGeometry(QgsPoint(2, 2)), "node2")
    geometry = QgsGeometry.fromMultiPolylineXY(
        [[QgsPointXY(1, 1), QgsPointXY(2, 2)], [QgsPointXY(3, 3), QgsPointXY(4, 4)]]
    )
    with pytest.raises(RuntimeError, match="All links must be single part lines"):
        index.snap_link(geometry)


def test_spatial_index_snap_link_invalid_geometry():
    index = _SpatialIndex()
    index.add_node(QgsGeometry(QgsPoint(1, 1)), "node1")
    index.add_node(QgsGeometry(QgsPoint(2, 2)), "node2")
    geometry = QgsGeometry()  # Invalid geometry
    with pytest.raises(RuntimeError, match="All links must have valid geometry"):
        index.snap_link(geometry)
