from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppSettings
from app.core.events import ApplicationEvents
from app.database.db import Database
from app.translation.secrets import SecretStore, SecretStoreError
from app.ui.widgets import Card


def _page_header(root: QVBoxLayout, title_text: str, subtitle_text: str) -> None:
    title = QLabel(title_text)
    title.setObjectName("PageTitle")
    subtitle = QLabel(subtitle_text)
    subtitle.setObjectName("PageSubtitle")
    root.addWidget(title)
    root.addWidget(subtitle)


class OverlaySettingsPage(QWidget):
    def __init__(self, settings: AppSettings, events: ApplicationEvents) -> None:
        super().__init__()
        self.settings = settings
        self.events = events
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(18)
        _page_header(root, "Overlay", "Tinh chỉnh cách bản dịch xuất hiện phía trên nội dung gốc")

        columns = QGridLayout()
        columns.setSpacing(16)
        form_card = Card("KIỂU HIỂN THỊ")
        form = QFormLayout()
        form.setSpacing(13)
        self.font = QFontComboBox()
        self.font.setCurrentFont(QFont(settings.overlay_font_family))
        self.size = QSpinBox()
        self.size.setRange(8, 48)
        self.size.setSuffix(" px")
        self.size.setValue(settings.overlay_font_size)
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(20, 100)
        self.opacity.setValue(round(settings.overlay_opacity * 100))
        self.opacity_label = QLabel(f"{self.opacity.value()}%")
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.opacity, 1)
        opacity_row.addWidget(self.opacity_label)
        self.spacing = QDoubleSpinBox()
        self.spacing.setRange(0.8, 2.0)
        self.spacing.setSingleStep(0.05)
        self.spacing.setValue(settings.overlay_line_spacing)
        self.cover = QCheckBox("Che vùng chữ gốc")
        self.cover.setChecked(settings.overlay_cover_source)
        self.background_button = QPushButton(settings.overlay_background)
        form.addRow("Font", self.font)
        form.addRow("Cỡ chữ", self.size)
        form.addRow("Độ trong suốt", opacity_row)
        form.addRow("Khoảng cách dòng", self.spacing)
        form.addRow("Màu nền", self.background_button)
        form.addRow("", self.cover)
        form_card.layout.addLayout(form)
        columns.addWidget(form_card, 0, 0)

        preview_card = Card("XEM TRƯỚC")
        self.preview = QLabel(
            "Đọc sách và tài liệu nước ngoài\n"
            "mà không làm gián đoạn mạch nội dung."
        )
        self.preview.setWordWrap(True)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(190)
        preview_card.layout.addWidget(self.preview)
        columns.addWidget(preview_card, 0, 1)
        columns.setColumnStretch(0, 1)
        columns.setColumnStretch(1, 1)
        root.addLayout(columns)

        save = QPushButton("Lưu cài đặt Overlay")
        save.setObjectName("PrimaryButton")
        save.setMaximumWidth(220)
        root.addWidget(save, alignment=Qt.AlignmentFlag.AlignRight)
        root.addStretch()

        self.opacity.valueChanged.connect(self._refresh_preview)
        self.font.currentFontChanged.connect(self._refresh_preview)
        self.size.valueChanged.connect(self._refresh_preview)
        self.background_button.clicked.connect(self._pick_background)
        save.clicked.connect(self._save)
        self._refresh_preview()

    def _pick_background(self) -> None:
        color = QColorDialog.getColor(QColor(self.background_button.text()), self)
        if color.isValid():
            self.background_button.setText(color.name().upper())
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        color = QColor(self.background_button.text())
        alpha = round(self.opacity.value() * 2.55)
        self.opacity_label.setText(f"{self.opacity.value()}%")
        self.preview.setFont(QFont(self.font.currentFont().family(), self.size.value()))
        self.preview.setStyleSheet(
            f"background: rgba({color.red()}, {color.green()}, {color.blue()}, {alpha});"
            "border: 1px solid #385174; border-radius: 10px; padding: 20px; color: #F2F7FF;"
        )

    def _save(self) -> None:
        self.settings.overlay_font_family = self.font.currentFont().family()
        self.settings.overlay_font_size = self.size.value()
        self.settings.overlay_opacity = self.opacity.value() / 100
        self.settings.overlay_background = self.background_button.text()
        self.settings.overlay_line_spacing = self.spacing.value()
        self.settings.overlay_cover_source = self.cover.isChecked()
        self.settings.save()
        self.events.settings_saved.emit()
        self.events.notice.emit("Đã lưu", "Cài đặt Overlay đã được lưu an toàn.")


class OCRSettingsPage(QWidget):
    def __init__(self, settings: AppSettings, events: ApplicationEvents) -> None:
        super().__init__()
        self.settings = settings
        self.events = events
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(18)
        _page_header(root, "OCR", "Cấu hình nhận dạng và phát hiện thay đổi màn hình")
        card = Card("PADDLEOCR · CẤU HÌNH CHUẨN BỊ")
        form = QFormLayout()
        self.model = QComboBox()
        self.model.addItems(["PP-OCRv5_mobile", "PP-OCRv5_server"])
        self.model.setCurrentText(settings.ocr_model)
        self.language = QComboBox()
        for label, code in (
            ("English", "en"),
            ("中文", "ch"),
            ("日本語", "japan"),
            ("한국어", "korean"),
        ):
            self.language.addItem(label, code)
        self.language.setCurrentIndex(max(0, self.language.findData(settings.ocr_language)))
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.0, 1.0)
        self.confidence.setSingleStep(0.05)
        self.confidence.setValue(settings.ocr_confidence_threshold)
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.001, 1.0)
        self.threshold.setDecimals(3)
        self.threshold.setSingleStep(0.005)
        self.threshold.setValue(settings.change_threshold)
        self.capture = QSpinBox()
        self.capture.setRange(100, 10_000)
        self.capture.setSuffix(" ms")
        self.capture.setValue(settings.capture_interval_ms)
        self.debounce = QSpinBox()
        self.debounce.setRange(100, 10_000)
        self.debounce.setSuffix(" ms")
        self.debounce.setValue(settings.ocr_debounce_ms)
        self.monitor = QSpinBox()
        self.monitor.setRange(0, 32)
        self.monitor.setSpecialValueText("Tất cả màn hình")
        self.monitor.setValue(settings.monitor_index)
        self.gpu = QCheckBox("Dùng GPU nếu Paddle hỗ trợ")
        self.gpu.setChecked(settings.ocr_use_gpu)
        self.excluded = QLineEdit()
        self.excluded.setText(", ".join(settings.excluded_processes))
        self.excluded.setPlaceholderText("1password.exe, keepass.exe")
        form.addRow("Model", self.model)
        form.addRow("Ngôn ngữ", self.language)
        form.addRow("Ngưỡng tin cậy", self.confidence)
        form.addRow("Ngưỡng thay đổi", self.threshold)
        form.addRow("Chu kỳ chụp", self.capture)
        form.addRow("Debounce OCR", self.debounce)
        form.addRow("Màn hình", self.monitor)
        form.addRow("Ứng dụng loại trừ", self.excluded)
        form.addRow("", self.gpu)
        card.layout.addLayout(form)
        note = QLabel(
            "Model English mobile mặc định đã được đóng gói sẵn và không cần tải mạng. "
            "Các ngôn ngữ/model khác sẽ cần tải vào thư mục dữ liệu ứng dụng. "
            "PP-OCRv5 server không hỗ trợ Korean; hãy dùng bản mobile cho Korean."
        )
        note.setWordWrap(True)
        note.setObjectName("PageSubtitle")
        card.layout.addWidget(note)
        root.addWidget(card)
        save = QPushButton("Lưu cài đặt OCR")
        save.setObjectName("PrimaryButton")
        save.setMaximumWidth(200)
        root.addWidget(save, alignment=Qt.AlignmentFlag.AlignRight)
        root.addStretch()
        save.clicked.connect(self._save)

    def _save(self) -> None:
        self.settings.ocr_model = self.model.currentText()
        self.settings.ocr_language = self.language.currentData()
        self.settings.ocr_confidence_threshold = self.confidence.value()
        self.settings.change_threshold = self.threshold.value()
        self.settings.capture_interval_ms = self.capture.value()
        self.settings.ocr_debounce_ms = self.debounce.value()
        self.settings.monitor_index = self.monitor.value()
        self.settings.ocr_use_gpu = self.gpu.isChecked()
        self.settings.excluded_processes = [
            item.strip().lower()
            for item in self.excluded.text().split(",")
            if item.strip()
        ]
        self.settings.save()
        self.events.settings_saved.emit()
        self.events.notice.emit("Đã lưu", "Cài đặt OCR đã được lưu.")


class TranslationSettingsPage(QWidget):
    def __init__(
        self,
        settings: AppSettings,
        events: ApplicationEvents,
        database: Database,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.events = events
        self.database = database
        self.secret_store = SecretStore()
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(18)
        _page_header(
            root,
            "Dịch thuật",
            "Mặc định chạy offline; DeepL/Google là tùy chọn nâng cao",
        )
        card = Card("PROVIDER")
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItem("Offline tích hợp · không cần API", "offline")
        self.provider.addItem("DeepL API", "deepl")
        self.provider.addItem("Google Cloud Translation", "google")
        self.provider.setCurrentIndex(max(0, self.provider.findData(settings.translation_provider)))
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Chỉ dùng trong phiên hiện tại")
        self.target = QComboBox()
        self.target.addItem("Tiếng Việt", "VI")
        self.target.addItem("English", "EN")
        self.target.addItem("日本語", "JA")
        self.target.setCurrentIndex(max(0, self.target.findData(settings.target_language)))
        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(3, 120)
        self.timeout.setSuffix(" giây")
        self.timeout.setValue(settings.request_timeout_seconds)
        self.rate_limit = QSpinBox()
        self.rate_limit.setRange(1, 1000)
        self.rate_limit.setSuffix(" / phút")
        self.rate_limit.setValue(settings.max_requests_per_minute)
        self.cache = QCheckBox("Bật Translation Cache")
        self.cache.setChecked(settings.cache_enabled)
        self.history = QCheckBox("Lưu lịch sử văn bản đã dịch")
        self.history.setChecked(settings.history_enabled)
        form.addRow("Provider", self.provider)
        form.addRow("API key", self.api_key)
        form.addRow("Ngôn ngữ đích", self.target)
        form.addRow("Timeout", self.timeout)
        form.addRow("Giới hạn yêu cầu", self.rate_limit)
        form.addRow("", self.cache)
        form.addRow("", self.history)
        card.layout.addLayout(form)
        self.privacy = QLabel(
            "Chế độ offline xử lý toàn bộ văn bản ngay trên máy và không gửi dữ liệu ra ngoài. "
            "Nếu chọn API, chỉ văn bản OCR được gửi; ảnh màn hình không bao giờ được gửi."
        )
        self.privacy.setWordWrap(True)
        self.privacy.setObjectName("PageSubtitle")
        card.layout.addWidget(self.privacy)
        row = QHBoxLayout()
        test = QPushButton("Kiểm tra kết nối")
        self.test_button = test
        clear_cache = QPushButton("Xóa cache")
        clear_cache.setObjectName("DangerButton")
        usage = sum(item.character_count for item in database.usage_totals())
        self.usage_label = QLabel(f"Đã gửi provider: {usage:,} ký tự")
        self.usage_label.setObjectName("PageSubtitle")
        save = QPushButton("Lưu cài đặt")
        save.setObjectName("PrimaryButton")
        row.addWidget(self.usage_label)
        row.addStretch()
        row.addWidget(clear_cache)
        row.addWidget(test)
        row.addWidget(save)
        root.addWidget(card)
        root.addLayout(row)
        root.addStretch()
        save.clicked.connect(self._save)
        test.clicked.connect(self._test)
        clear_cache.clicked.connect(self._clear_cache)
        self.provider.currentIndexChanged.connect(self._update_key_status)
        self._update_key_status()

    def _update_key_status(self) -> None:
        offline = self.provider.currentData() == "offline"
        self.api_key.setEnabled(not offline)
        self.timeout.setEnabled(not offline)
        self.rate_limit.setEnabled(not offline)
        self.target.setEnabled(not offline)
        self.test_button.setText("Kiểm tra model offline" if offline else "Kiểm tra kết nối")
        if offline:
            vietnamese = self.target.findData("VI")
            if vietnamese >= 0:
                self.target.setCurrentIndex(vietnamese)
            self.api_key.clear()
            self.api_key.setPlaceholderText("Không cần API key")
            self.usage_label.setText("Offline: không gửi dữ liệu ra ngoài")
            return
        try:
            has_key = bool(self.secret_store.get(self.provider.currentData()))
        except SecretStoreError:
            has_key = False
        self.api_key.setPlaceholderText(
            "Đã lưu trong Windows Credential Manager"
            if has_key
            else "Nhập API key"
        )
        usage = sum(item.character_count for item in self.database.usage_totals())
        self.usage_label.setText(f"Đã gửi provider: {usage:,} ký tự")

    def _save(self, _checked: bool = False, *, show_notice: bool = True) -> bool:
        self.settings.translation_provider = self.provider.currentData()
        self.settings.target_language = self.target.currentData()
        self.settings.request_timeout_seconds = self.timeout.value()
        self.settings.max_requests_per_minute = self.rate_limit.value()
        self.settings.cache_enabled = self.cache.isChecked()
        self.settings.history_enabled = self.history.isChecked()
        try:
            key = self.api_key.text().strip()
            if key and self.settings.translation_provider != "offline":
                self.secret_store.set(self.settings.translation_provider, key)
            self.settings.save()
        except (OSError, SecretStoreError) as exc:
            self.events.notice.emit("Không thể lưu", str(exc))
            return False
        self.api_key.clear()
        self._update_key_status()
        self.events.settings_saved.emit()
        if show_notice:
            message = (
                "Đã chọn dịch offline; không cần API key hoặc kết nối Internet."
                if self.settings.translation_provider == "offline"
                else "Tùy chọn đã lưu; API key nằm trong Windows Credential Manager."
            )
            self.events.notice.emit(
                "Đã lưu",
                message,
            )
        return True

    def _test(self) -> None:
        if self._save(show_notice=False):
            self.test_button.setEnabled(False)
            self.events.test_translation_requested.emit()
            QTimer.singleShot(3000, lambda: self.test_button.setEnabled(True))

    def _clear_cache(self) -> None:
        answer = QMessageBox.question(
            self,
            "Xóa Translation Cache",
            "Xóa toàn bộ bản dịch đã cache? Lịch sử không bị ảnh hưởng.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.database.clear_cache()
            self.events.notice.emit("Đã xóa", "Translation Cache hiện đang trống.")

