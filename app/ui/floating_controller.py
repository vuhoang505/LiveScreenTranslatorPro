from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.events import ApplicationEvents, RuntimeStatus
from app.overlay.overlay_window import exclude_window_from_capture


class FloatingController(QWidget):
    def __init__(self, events: ApplicationEvents) -> None:
        super().__init__()
        self.events = events
        self._drag_offset = QPoint()
        self._collapsed = False
        self.setWindowTitle("LiveScreen Controller")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(330)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("Card")
        root.addWidget(panel)
        body = QVBoxLayout(panel)
        body.setContentsMargins(12, 10, 12, 10)

        header = QHBoxLayout()
        brand = QLabel("LiveScreen")
        brand.setStyleSheet("font-weight: 700; color: #67E8F1;")
        self.status = QLabel("Sẵn sàng")
        self.status.setObjectName("StatusGood")
        self.collapse_button = QPushButton("—")
        self.collapse_button.setFixedSize(30, 26)
        header.addWidget(brand)
        header.addWidget(self.status, 1)
        header.addWidget(self.collapse_button)
        body.addLayout(header)

        self.controls = QWidget()
        controls_layout = QHBoxLayout(self.controls)
        controls_layout.setContentsMargins(0, 4, 0, 0)
        self.start = QPushButton("▶ Bắt đầu")
        self.start.setObjectName("PrimaryButton")
        self.pause = QPushButton("⏸ Tạm dừng")
        self.clear = QPushButton("✕ Xóa")
        self.settings = QPushButton("⚙ Cài đặt")
        self.start.setToolTip("Bắt đầu dịch màn hình")
        self.pause.setToolTip("Tạm dừng hoặc tiếp tục")
        self.clear.setToolTip("Xóa toàn bộ bản dịch đang phủ trên màn hình")
        controls_layout.addWidget(self.start)
        controls_layout.addWidget(self.pause)
        controls_layout.addWidget(self.clear)
        controls_layout.addWidget(self.settings)
        body.addWidget(self.controls)

        self.start.clicked.connect(events.start)
        self.pause.clicked.connect(events.toggle_pause)
        self.clear.clicked.connect(events.clear_overlay_requested)
        self.settings.clicked.connect(events.show_settings_requested)
        self.collapse_button.clicked.connect(self._toggle_collapsed)
        events.status_changed.connect(self._status_changed)
        events.pipeline_status_changed.connect(self._pipeline_status_changed)
        self._status_changed(events.status.value)

    def _toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self.controls.setVisible(not self._collapsed)
        self.collapse_button.setText("+" if self._collapsed else "—")
        self.adjustSize()

    def _status_changed(self, value: str) -> None:
        status = RuntimeStatus(value)
        self.status.setText(
            {
                RuntimeStatus.UNAVAILABLE: "UI sẵn sàng",
                RuntimeStatus.STOPPED: "Đã dừng",
                RuntimeStatus.RUNNING: "Đang dịch",
                RuntimeStatus.PAUSED: "Tạm dừng",
            }[status]
        )
        enabled = self.events.engine_available
        self.start.setEnabled(enabled and status is RuntimeStatus.STOPPED)
        self.pause.setEnabled(enabled and status is not RuntimeStatus.STOPPED)
        self.clear.setEnabled(enabled)
        if status is RuntimeStatus.RUNNING:
            self.start.setText("● Đang dịch")
            self.start.setObjectName("RunningButton")
            self.pause.setText("⏸ Tạm dừng")
            self.pause.setObjectName("PauseButton")
        elif status is RuntimeStatus.PAUSED:
            self.start.setText("⏸ Đã tạm dừng")
            self.start.setObjectName("RunningButton")
            self.pause.setText("▶ Tiếp tục")
            self.pause.setObjectName("ResumeButton")
        else:
            self.start.setText("▶ Bắt đầu")
            self.start.setObjectName("PrimaryButton")
            self.pause.setText("⏸ Tạm dừng")
            self.pause.setObjectName("PauseButton")
        for button in (self.start, self.pause):
            button.style().unpolish(button)
            button.style().polish(button)

    def _pipeline_status_changed(self, title: str, _detail: str) -> None:
        if self.events.status is RuntimeStatus.RUNNING:
            self.status.setText(title)
            self.start.setText("⏳ Đang xử lý" if title == "Đang xử lý" else "● Đang dịch")

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        exclude_window_from_capture(int(self.winId()))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()


