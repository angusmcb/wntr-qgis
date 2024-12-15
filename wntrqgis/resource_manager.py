"""
Contains utility methods for accessing the items in the resources section.
"""

from enum import Enum
from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QPainter, QPixmap

RESOURCES_PATH = Path(__file__).resolve().parent / "resources"


class WqIcon(Enum):
    NEW = "mActionFileNew.svg"
    OPEN = "mActionFileOpen.svg"
    RUN = "lightning-svgrepo-com.svg"
    # LOGO = "wntr-favicon.svg"
    #  LOGO = "water_circle.png"
    LOGO = "logo.svg"

    @property
    def path(self):
        return RESOURCES_PATH / "icons" / self.value

    @property
    def q_pixmap(self):
        return QIcon(str(self.path)).pixmap(128, 128)  # QPixmap(128,128).convertFromImage(str(self.path))

    @property
    def q_icon(self):
        return QIcon(self.q_pixmap)


class WqExampleInp(Enum):
    KY1 = "ky1.inp"
    KY10 = "ky10.inp"

    @property
    def path(self):
        return RESOURCES_PATH / "examples" / self.value


def join_pixmap(p1, p2, mode=QPainter.CompositionMode_SourceOver):
    # s = p1.size().expandedTo(p2.size())
    result = QPixmap(128, 128)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.drawPixmap(0, 0, 128, 128, p1)
    painter.setCompositionMode(mode)
    # painter.drawPixmap(result.rect(), p2, p2.rect())
    painter.drawPixmap(64, 64, 64, 64, p2)
    painter.end()
    return result
