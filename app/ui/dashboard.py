from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppSettings
from app.core.events import ApplicationEvents, RuntimeStatus
from app.ui.widgets import ActivityGraph, Card, MetricCard


class DashboardPage(QWidget):
    def __init__(self, settings: AppSettings, events: ApplicationEvents) -> None:
        super().__init__()
        self.settings = settings
        self.events = events

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(18)

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Trung tâm điều khiển dịch nội dung đang hiển thị trên màn hình")
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        command_card = Card()
        command_row = QHBoxLayout()
        status_column = QVBoxLayout()
        status_label = QLabel("TRẠNG THÁI QUYỀN RIÊNG TƯ")
        status_label.setObjectName("CardTitle")
        self.runtime_status = QLabel("Chưa quan sát màn hình")
        self.runtime_status.setObjectName("StatusGood")
        self.runtime_detail = QLabel("Sẵn sàng · Chưa chụp hoặc gửi nội dung màn hình")
        self.runtime_detail.setObjectName("PageSubtitle")
        status_column.addWidget(status_label)
        status_column.addWidget(self.runtime_status)
        status_column.addWidget(self.runtime_detail)
        command_row.addLayout(status_column, 1)

        self.source_language = QComboBox()
        self.source_language.addItem("Tự động", "auto")
        self.source_language.addItem("English", "EN")
        self.source_language.addItem("中文", "ZH")
        self.source_language.addItem("日本語", "JA")
        self.source_language.addItem("한국어", "KO")
        self.source_language.setCurrentIndex(
            max(0, self.source_language.findData(settings.source_language))
        )
        self.target_language = QComboBox()
        self.target_language.addItem("Tiếng Việt", "VI")
        self.target_language.addItem("English", "EN")
        self.target_language.addItem("日本語", "JA")
        self.target_language.setCurrentIndex(
            max(0, self.target_language.findData(settings.target_language))
        )
        command_row.addWidget(self.source_language)
        command_row.addWidget(QLabel("→"))
        command_row.addWidget(self.target_language)

        self.start_button = QPushButton("▶  Bắt đầu dịch")
        self.start_button.setObjectName("PrimaryButton")
        self.stop_button = QPushButton("■  Dừng")
        self.stop_button.setObjectName("DangerButton")
        self.pause_button = QPushButton("⏸  Tạm dừng")
        self.start_button.setToolTip("Bắt đầu đọc và dịch nội dung trên màn hình")
        self.pause_button.setToolTip("Tạm ngừng hoặc tiếp tục theo dõi màn hình")
        self.stop_button.setToolTip("Dừng hoàn toàn phiên dịch hiện tại")
        command_row.addWidget(self.start_button)
        command_row.addWidget(self.pause_button)
        command_row.addWidget(self.stop_button)
        command_card.layout.addLayout(command_row)
        root.addWidget(command_card)

        metric_grid = QGridLayout()
        metric_grid.setSpacing(14)
        self.segment_metric = MetricCard("ĐOẠN ĐÃ DỊCH", "0", "Phiên hiện tại")
        self.latency_metric = MetricCard("XỬ LÝ GẦN NHẤT", "—", "Chưa có dữ liệu")
        self.ocr_metric = MetricCard("OCR ENGINE", "Sẵn sàng", "Model tải khi dùng lần đầu")
        self.api_metric = MetricCard(
            "BỘ DỊCH", "Offline", "Có sẵn · không cần API"
        )
        for index, card in enumerate(
            (self.segment_metric, self.latency_metric, self.ocr_metric, self.api_metric)
        ):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            metric_grid.addWidget(card, 0, index)
        root.addLayout(metric_grid)

        graph_card = Card("HOẠT ĐỘNG 60 GIÂY GẦN NHẤT")
        graph_card.layout.addWidget(ActivityGraph())
        graph_caption = QLabel(
            "Biểu đồ sẽ hiển thị số vùng OCR và yêu cầu dịch sau khi pipeline được tích hợp."
        )
        graph_caption.setObjectName("PageSubtitle")
        graph_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graph_card.layout.addWidget(graph_caption)
        root.addWidget(graph_card, 1)

        self.start_button.clicked.connect(events.start)
        self.stop_button.clicked.connect(events.stop)
        self.pause_button.clicked.connect(events.toggle_pause)
        self.source_language.currentIndexChanged.connect(self._languages_changed)
        self.target_language.currentIndexChanged.connect(self._languages_changed)
        events.status_changed.connect(self._on_status_changed)
        events.pipeline_status_changed.connect(self._on_pipeline_status)
        events.metrics_updated.connect(self._on_metrics)
        events.settings_saved.connect(self._sync_provider_controls)
        self._sync_provider_controls()
        self._on_status_changed(events.status.value)

    def _languages_changed(self) -> None:
        self.settings.source_language = self.source_language.currentData()
        self.settings.target_language = self.target_language.currentData()

    def _sync_provider_controls(self) -> None:
        offline = self.settings.translation_provider == "offline"
        if offline:
            self.source_language.setCurrentIndex(
                max(0, self.source_language.findData("auto"))
            )
            self.target_language.setCurrentIndex(
                max(0, self.target_language.findData("VI"))
            )
        self.source_language.setEnabled(not offline)
        self.target_language.setEnabled(not offline)

    def _on_status_changed(self, value: str) -> None:
        status = RuntimeStatus(value)
        labels = {
            RuntimeStatus.UNAVAILABLE: ("Chưa quan sát màn hình", "StatusGood"),
            RuntimeStatus.STOPPED: ("Đã dừng", "StatusGood"),
            RuntimeStatus.RUNNING: ("Đang quan sát màn hình", "StatusMuted"),
            RuntimeStatus.PAUSED: ("Đã tạm dừng", "StatusMuted"),
        }
        text, style = labels[status]
        self.runtime_status.setText(text)
        self.runtime_status.setObjectName(style)
        self.runtime_status.style().unpolish(self.runtime_status)
        self.runtime_status.style().polish(self.runtime_status)
        enabled = self.events.engine_available
        self.start_button.setEnabled(enabled and status is RuntimeStatus.STOPPED)
        self.stop_button.setEnabled(enabled and status is not RuntimeStatus.STOPPED)
        self.pause_button.setEnabled(enabled and status is not RuntimeStatus.STOPPED)
        if status is RuntimeStatus.RUNNING:
            self.start_button.setText("●  Đang dịch")
            self.start_button.setObjectName("RunningButton")
            self.pause_button.setText("⏸  Tạm dừng")
            self.pause_button.setObjectName("PauseButton")
        elif status is RuntimeStatus.PAUSED:
            self.start_button.setText("⏸  Đã tạm dừng")
            self.start_button.setObjectName("RunningButton")
            self.pause_button.setText("▶  Tiếp tục")
            self.pause_button.setObjectName("ResumeButton")
        else:
            self.start_button.setText("▶  Bắt đầu dịch")
            self.start_button.setObjectName("PrimaryButton")
            self.pause_button.setText("⏸  Tạm dừng")
            self.pause_button.setObjectName("PauseButton")
        for button in (self.start_button, self.pause_button, self.stop_button):
            button.style().unpolish(button)
            button.style().polish(button)

    def _on_pipeline_status(self, title: str, detail: str) -> None:
        self.runtime_status.setText(title)
        self.runtime_detail.setText(detail)
        if title.startswith("Lỗi"):
            self.runtime_status.setObjectName("StatusMuted")
        self.runtime_status.style().unpolish(self.runtime_status)
        self.runtime_status.style().polish(self.runtime_status)
        if self.events.status is RuntimeStatus.RUNNING:
            self.start_button.setText(
                "⏳  Đang xử lý…" if title == "Đang xử lý" else "●  Đang dịch"
            )

    def _on_metrics(self, segments: int, elapsed_seconds: float, characters: int) -> None:
        self.segment_metric.value_label.setText(str(segments))
        self.latency_metric.value_label.setText(f"{elapsed_seconds:.2f}s")
        self.latency_metric.caption_label.setText("Pipeline gần nhất")
        self.ocr_metric.value_label.setText("Sẵn sàng")
        self.ocr_metric.caption_label.setText("PaddleOCR cục bộ")
        if self.settings.translation_provider == "offline":
            self.api_metric.value_label.setText("Offline")
            self.api_metric.caption_label.setText("Xử lý cục bộ · không gửi dữ liệu")
        else:
            self.api_metric.value_label.setText(f"{characters:,}")
            self.api_metric.caption_label.setText("Ký tự đã gửi provider")

