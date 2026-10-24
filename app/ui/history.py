from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppSettings
from app.core.events import ApplicationEvents
from app.database.db import Database
from app.database.models import HistoryRecord
from app.ui.widgets import Card


class HistoryPage(QWidget):
    def __init__(
        self, settings: AppSettings, database: Database, events: ApplicationEvents
    ) -> None:
        super().__init__()
        self.settings = settings
        self.database = database
        self.events = events
        self._records: list[HistoryRecord] = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self.refresh)

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(18)
        title = QLabel("Lịch sử")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Các đoạn đã dịch được lưu cục bộ; không lưu ảnh màn hình")
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm trong văn bản gốc hoặc bản dịch…")
        copy = QPushButton("Sao chép")
        export_txt = QPushButton("Xuất TXT")
        export_json = QPushButton("Xuất JSON")
        clear = QPushButton("Xóa lịch sử")
        clear.setObjectName("DangerButton")
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(copy)
        toolbar.addWidget(export_txt)
        toolbar.addWidget(export_json)
        toolbar.addWidget(clear)
        root.addLayout(toolbar)

        card = Card()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Thời gian", "Văn bản gốc", "Bản dịch", "Provider"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        card.layout.addWidget(self.table)
        root.addWidget(card, 1)

        self.search.textChanged.connect(lambda _text: self._search_timer.start())
        copy.clicked.connect(self._copy_selected)
        export_txt.clicked.connect(lambda: self._export("txt"))
        export_json.clicked.connect(lambda: self._export("json"))
        clear.clicked.connect(self._clear)
        events.history_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        self._records = self.database.history(self.search.text())
        self.table.setRowCount(len(self._records))
        for row_index, record in enumerate(self._records):
            values = (
                record.created_at,
                record.source_text,
                record.translated_text,
                record.provider,
            )
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(value))

    def _copy_selected(self) -> None:
        selected = self.table.currentRow()
        if 0 <= selected < len(self._records):
            record = self._records[selected]
            QGuiApplication.clipboard().setText(
                f"{record.source_text}\n\n{record.translated_text}"
            )

    def _export(self, file_type: str) -> None:
        if not self._records:
            self.events.notice.emit("Không có dữ liệu", "Lịch sử hiện đang trống.")
            return
        default_name = f"translation-history.{file_type}"
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất lịch sử",
            default_name,
            "Text (*.txt)" if file_type == "txt" else "JSON (*.json)",
        )
        if not selected:
            return
        path = Path(selected)
        if file_type == "json":
            payload = [
                {
                    "source_text": item.source_text,
                    "translated_text": item.translated_text,
                    "source_language": item.source_language,
                    "target_language": item.target_language,
                    "provider": item.provider,
                    "created_at": item.created_at,
                }
                for item in self._records
            ]
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        else:
            content = "\n\n".join(
                f"[{item.created_at}] {item.provider}\n"
                f"Gốc: {item.source_text}\nDịch: {item.translated_text}"
                for item in self._records
            )
            path.write_text(content, encoding="utf-8")
        self.events.notice.emit("Đã xuất", str(path))

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self,
            "Xóa lịch sử",
            "Xóa toàn bộ lịch sử dịch? Cache không bị ảnh hưởng.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.database.clear_history()
            self.refresh()

