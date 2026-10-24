from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QFontMetrics


def fitted_font(
    text: str,
    rect: QRect,
    family: str,
    preferred_size: int,
    minimum_size: int = 8,
) -> QFont:
    flags = Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft
    for size in range(preferred_size, minimum_size - 1, -1):
        font = QFont(family, size)
        metrics = QFontMetrics(font)
        required = metrics.boundingRect(rect, int(flags), text)
        if required.height() <= rect.height() and required.width() <= rect.width():
            return font
    return QFont(family, minimum_size)

