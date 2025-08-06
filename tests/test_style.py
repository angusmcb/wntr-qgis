from unittest.mock import MagicMock

import pytest
from qgis.core import QgsDefaultValue, QgsEditorWidgetSetup, QgsField, QgsVectorLayer

from wntrqgis.elements import Field, ModelLayer
from wntrqgis.style import _FieldStyler, style
from wntrqgis.units import UnitNames


@pytest.fixture
def mock_layer():
    layer = MagicMock(spec=QgsVectorLayer)
    layer.fields.return_value = [
        QgsField("name"),
        QgsField("diameter"),
        QgsField("roughness"),
        QgsField("minor_loss"),
        QgsField("base_speed"),
        QgsField("power"),
    ]
    return layer


@pytest.fixture(params=list(Field))
def field(request):
    return request.param


@pytest.fixture
def field_styler(field: Field):
    units = UnitNames()
    return _FieldStyler(field, ModelLayer.PIPES, None, units)


def test_style_function(mock_layer):
    style(mock_layer, ModelLayer.PIPES)

    mock_layer.setRenderer.assert_called()
    mock_layer.setLabeling.assert_called()
    assert mock_layer.setFieldAlias.call_count == len(mock_layer.fields())
    assert mock_layer.setEditorWidgetSetup.call_count == len(mock_layer.fields())
    assert mock_layer.setDefaultValueDefinition.call_count == len(mock_layer.fields())
    assert mock_layer.setConstraintExpression.call_count == len(mock_layer.fields())


def test_field_styler_editor_widget(field_styler: _FieldStyler):
    widget = field_styler.editor_widget

    assert isinstance(widget, QgsEditorWidgetSetup)


def test_field_styler_default_value(field_styler: _FieldStyler):
    default_value = field_styler.default_value
    assert isinstance(default_value, QgsDefaultValue)


def test_field_styler_alias(field_styler: _FieldStyler):
    alias = field_styler.alias

    assert isinstance(alias, str)


def test_field_styler_constraint(field_styler: _FieldStyler):
    constraint = field_styler.constraint

    assert isinstance(constraint, tuple)
    assert len(constraint) == 2
    assert isinstance(constraint[0], str) or constraint[0] is None
    assert isinstance(constraint[1], str) or constraint[1] is None
