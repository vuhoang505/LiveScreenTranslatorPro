from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class Card(QFrame):
    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 16)
        self.layout.setSpacing(10)
        if title:
            label = QLabel(title)
            label.setObjectName("CardTitle")
            self.layout.addWidget(label)


class MetricCard(Card):
    def __init__(self, title: str, value: str, caption: str) -> None:
        super().__init__(title)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("Metric")
        self.caption_label = QLabel(caption)
        self.caption_label.setObjectName("PageSubtitle")
        self.layout.addWidget(self.value_label)
        self.layout.addWidget(self.caption_label)


class ActivityGraph(QWidget):
    def __init__(self, values: Iterable[int] | None = None) -> None:
        super().__init__()
        self.values = list(values or [0] * 22)
        self.setMinimumHeight(120)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0C182A"))
        if len(self.values) < 2:
            return
        maximum = max(max(self.values), 1)
        width = max(self.width() - 24, 1)
        height = max(self.height() - 24, 1)
        path = QPainterPath()
        for index, value in enumerate(self.values):
            point = QPointF(
                12 + index * width / (len(self.values) - 1),
                12 + height * (1 - value / maximum),
            )
            path.moveTo(point) if index == 0 else path.lineTo(point)
        painter.setPen(QPen(QColor("#54E5F0"), 2.2, Qt.PenStyle.SolidLine))
        painter.drawPath(path)

