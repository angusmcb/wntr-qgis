import pytest
from qgis.PyQt.QtGui import QIcon

ICON_PATH = ":images/icons/qgis_icon.svg"


def test_assert_valid_icon(assert_valid_qicon):
    icon = QIcon(ICON_PATH)
    assert_valid_qicon(icon)


def test_assert_valid_icon_not_valid(assert_valid_qicon):
    icon = QIcon(":images/icons/not_a_real_icon.svg")
    with pytest.raises(AssertionError):
        assert_valid_qicon(icon)
