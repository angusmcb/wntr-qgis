"""
Contains utility methods for accessing the items in the resources section.
"""

import enum
import pathlib

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QPainter, QPixmap

RESOURCES_PATH = pathlib.Path(__file__).resolve().parent / "resources"


class WqIcon(enum.Enum):
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


def _inp_path(example_name: str) -> str:
    return str(RESOURCES_PATH / "examples" / (example_name + ".inp"))


examples = {
    "KY1": _inp_path("ky1"),
    "KY10": _inp_path("ky10"),
    "VALVES": _inp_path("valves"),
}

"""
class Example:
    A namespace for  easily accessing file path of examples

    Can be used directly to create a WNTR ``WaterNetworkModel``

    The actual value of the path will vary from one system to another.

    >>> import wntrqgis as wq
    >>> wq.Example.KY1
    '...examples\\\\ky1.inp'

    >>> import wntr
    >>> wn = wntr.network.WaterNetworkModel(wq.Example.KY1)

    KY1: str = _inp_path("ky1")
    KY1 from Kentucky University

    :meta hide-value:

    KY10: str = _inp_path("ky10")
    KY10 from kentucky

    Dataset from `Kentucky Water Research Institute <https://uknowledge.uky.edu/wdst/12/>`_.
    Slightly modified to eliminate overlapping nodes to make it spatial-compatible.



    :meta hide-value:

    VALVES: str = _inp_path("valves")
    Valves

    An example of all the different valve available.

    :meta hide-value:

"""


#     The pathlib.Path object is available with:
#         wntrqgis.Example
#     Files include:
#     * ky1.inp
#     * ky10.inp"""
#     return str(RESOURCES_PATH / "examples" / file)


# class FileEnumMeta(enum.EnumMeta):
#     def __repr__(self):
#         return "\n".join([f"{name}: {value}" for name, value in self.__members__.items()])


# class Inp(enum.Enum):
#     KY1 = "ky1"
#     KY10 = "ky10"

#     def __new__(cls, *args):
#         obj = object.__new__(cls)
#         obj._value_ = RESOURCES_PATH / "examples" / args[0]
#         obj.fname = args[0]
#         return obj

#     def __repr__(self):
#         return f"<Inp.{self.name}: Path('.../examples/{self.fname}.inp')>"


# try:
#     _StrEnum = enum.StrEnum
# except AttributeError:

#     class _StrEnum(str, enum.Enum):
#         pass


# class Example2(_StrEnum):
#     """Get an example file path.

#     Can be loaded directly into WNTR

#     >>> wntr.network.WaterNetworkModel(wntrqgis.Example.KY10)"""

#     KY1 = "ky1", "An example from ky"

#     KY10 = "ky10", """An example from kentucky !s"""

#     def __new__(cls, *args):
#         value = str(RESOURCES_PATH / "examples" / args[0])
#         obj = str.__new__(cls, value)
#         obj._value_ = value
#         obj.fname = args[0]
#         obj.__doc__ = args[1]
#         return obj

#     def __repr__(self):
#         return f"<Inp.{self.name}: '.../examples/{self.fname}.inp'>"


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
