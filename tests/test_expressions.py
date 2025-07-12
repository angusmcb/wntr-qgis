from datetime import datetime, timedelta

import pytest
from qgis.core import (
    QgsDateTimeRange,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsTemporalNavigationObject,
)

import wntrqgis.expressions  # noqa: F401


def test_curve_ok():
    expr = QgsExpression("wntr_check_curve('(1,2), (3,4)')")
    assert expr.hasParserError() is False
    assert expr.evaluate() is True
    assert expr.hasEvalError() is False


def test_curve_wrong():
    expr = QgsExpression("wntr_check_curve('(x,y)')")
    assert expr.hasParserError() is False
    assert expr.evaluate() is False
    assert expr.hasEvalError() is False


@pytest.mark.parametrize("none_value", ["NULL", "''", "'  '"])
def test_curve_null(none_value):
    expr = QgsExpression(f"wntr_check_curve({none_value})")
    assert expr.hasParserError() is False
    assert expr.evaluate() is None
    assert expr.hasEvalError() is False


def test_pattern_ok():
    expr = QgsExpression("wntr_check_pattern('1 2 3')")
    assert expr.hasParserError() is False
    assert expr.evaluate() is True
    assert expr.hasEvalError() is False


def test_pattern_wrong():
    expr = QgsExpression("wntr_check_pattern('x y z')")
    assert expr.hasParserError() is False
    assert expr.evaluate() is False
    assert expr.hasEvalError() is False


@pytest.mark.parametrize("none_value", ["NULL", "''", "'  '"])
def test_pattern_null(none_value):
    expr = QgsExpression(f"wntr_check_pattern({none_value})")
    assert expr.hasParserError() is False
    assert expr.evaluate() is None
    assert expr.hasEvalError() is False


@pytest.fixture
def expression_context(qgis_iface):
    """
    Fixture to provide a QgsExpressionContext with a temporal navigation object.
    This is useful for testing expressions that depend on the current time.
    """
    context = QgsExpressionContext()
    start = datetime(2000, 1, 1, 0, 0, 0)
    datetime_range = QgsDateTimeRange(start, start + timedelta(hours=24))

    current_time = start + timedelta(hours=1)

    temporal_controller = QgsTemporalNavigationObject()
    temporal_controller.setTemporalExtents(datetime_range)
    context.appendScope(temporal_controller.createExpressionContextScope())

    qgis_iface.mapCanvas().setTemporalRange(QgsDateTimeRange(current_time, current_time + timedelta(hours=1)))
    context.appendScope(QgsExpressionContextUtils.mapSettingsScope(qgis_iface.mapCanvas().mapSettings()))

    return context


def test_result_no_context():
    expr = QgsExpression("wntr_result_at_current_time(array(0, 1, 2))")
    assert expr.hasParserError() is False
    assert expr.evaluate() == 0.0
    assert expr.hasEvalError() is False


def test_result_empty_context():
    expr = QgsExpression("wntr_result_at_current_time(array(0, 1, 2))")
    assert expr.hasParserError() is False
    assert expr.evaluate(QgsExpressionContext()) == 0.0
    assert expr.hasEvalError() is False


def test_result_at_current_time_ok(expression_context):
    expr = QgsExpression("wntr_result_at_current_time(array(0,1,2))")
    assert expr.hasParserError() is False
    assert expr.evaluate(expression_context) == 1.0
    assert expr.hasEvalError() is False
