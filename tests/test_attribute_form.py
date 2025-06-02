import pytest
from pytest_qgis import QgisBot
from qgis.core import QgsGeometry

from wntrqgis import from_qgis, to_qgis


@pytest.fixture(scope="class")
def template_layers():
    import wntr

    wn = wntr.network.WaterNetworkModel()
    layers = to_qgis(wn)
    for layer in layers.values():
        layer.startEditing()
    return layers


class TestFormHasNoWarnings:
    @pytest.mark.parametrize("layer_type", ["RESERVOIRS", "JUNCTIONS", "TANKS"])
    def test_points(self, qgis_bot: QgisBot, template_layers, layer_type):
        layer = template_layers[layer_type]
        qgis_bot.create_feature_with_attribute_dialog(
            layer, QgsGeometry.fromWkt("POINT(0,0)"), raise_from_warnings=True
        )

    @pytest.mark.parametrize("layer_type", ["PIPES", "VALVES", "PUMPS"])
    def test_lines(self, qgis_bot: QgisBot, template_layers, layer_type):
        layer = template_layers[layer_type]
        qgis_bot.create_feature_with_attribute_dialog(
            layer, QgsGeometry.fromWkt("LINESTRING (0 0, 0 1, 1 2)"), raise_from_warnings=True
        )


@pytest.mark.parametrize(
    "name_string",
    [
        "a" * 32,  # Invalid name length
        "name with spaces",  # Invalid name characters
    ],
)
class TestWarnsWithWrongName:
    @pytest.mark.parametrize("layer_type", ["RESERVOIRS", "JUNCTIONS", "TANKS"])
    def test_points(self, qgis_bot: QgisBot, template_layers, layer_type, name_string):
        layer = template_layers[layer_type]
        with pytest.raises(ValueError, match="Name must"):
            qgis_bot.create_feature_with_attribute_dialog(
                layer, QgsGeometry.fromWkt("POINT(0,0)"), {"name": name_string}, raise_from_warnings=True
            )

    @pytest.mark.parametrize("layer_type", ["PIPES", "VALVES", "PUMPS"])
    def test_lines(self, qgis_bot: QgisBot, template_layers, layer_type, name_string):
        layer = template_layers[layer_type]
        with pytest.raises(ValueError, match="Name must"):
            qgis_bot.create_feature_with_attribute_dialog(
                layer,
                QgsGeometry.fromWkt("LINESTRING (0 0, 0 1, 1 2)"),
                {"name": name_string},
                raise_from_warnings=True,
            )


def test_creates_valid_model(qgis_bot: QgisBot, template_layers):
    qgis_bot.create_feature_with_attribute_dialog(template_layers["RESERVOIRS"], QgsGeometry.fromWkt("POINT(0 0)"))
    qgis_bot.create_feature_with_attribute_dialog(template_layers["JUNCTIONS"], QgsGeometry.fromWkt("POINT(0 1)"))
    qgis_bot.create_feature_with_attribute_dialog(template_layers["JUNCTIONS"], QgsGeometry.fromWkt("POINT(0 2)"))
    qgis_bot.create_feature_with_attribute_dialog(template_layers["TANKS"], QgsGeometry.fromWkt("POINT(0 3)"))

    qgis_bot.create_feature_with_attribute_dialog(
        template_layers["PIPES"], QgsGeometry.fromWkt("LINESTRING (0 0, 0 1)")
    )
    qgis_bot.create_feature_with_attribute_dialog(
        template_layers["VALVES"], QgsGeometry.fromWkt("LINESTRING (0 1, 0 2)")
    )
    qgis_bot.create_feature_with_attribute_dialog(
        template_layers["PUMPS"], QgsGeometry.fromWkt("LINESTRING (0 2, 0 3)")
    )

    wn2 = from_qgis(template_layers, units="LPS", headloss="H-W")

    import wntr

    sim = wntr.sim.EpanetSimulator(wn2)
    results = sim.run_sim()

    assert results
