from typing import Any

from qgis.PyQt.QtWidgets import QApplication


def tr(
    text: str,
    disambiguation: str = "",
    n=-1,
    context: str = "@default",
) -> str:
    """Get the translation for a string using Qt translation API.

    We implement this ourselves since we do not inherit QObject.

    :param text: String for translation.
    :param args: arguments to use in formatting.
    :param context: Context of the translation.
    :param kwargs: keyword arguments to use in formatting.

    :returns: Translated version of message.
    """
    # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
    return QApplication.translate(context, text, disambiguation, n)
