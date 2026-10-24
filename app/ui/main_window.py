from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.core.config import AppSettings
from app.core.events import ApplicationEvents
from app.database.db import Database
from app.overlay.overlay_window import exclude_window_from_capture
from app.ui.dashboard import DashboardPage
from app.ui.floating_controller import FloatingController
from app.ui.history import HistoryPage
from app.ui.settings import OCRSettingsPage, OverlaySettingsPage, TranslationSettingsPage


class MainWindow(QMainWindow):
    def __init__(
        self, settings: AppSettings, events: ApplicationEvents, database: Database
    ) -> None:
        super().__init__()
        self.app_settings = settings
        self.events = events
        self.database = database
        self.runtime_controller = None
        self.hotkey_manager = None
        self.window_settings = QSettings("LiveScreenTranslator", "LiveScreenTranslatorPro")
        self.setWindowTitle(settings.app_name)
        self.setMinimumSize(1040, 680)
        self.resize(1240, 780)

        root_widget = QWidget()
        root_widget.setObjectName("AppRoot")
        self.setCentralWidget(root_widget)
        root = QHBoxLayout(root_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(224)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 24, 18, 18)
        side.setSpacing(7)
        brand = QLabel("LiveScreen")
        brand.setObjectName("Brand")
        accent = QLabel("TRANSLATOR PRO")
        accent.setObjectName("BrandAccent")
        side.addWidget(brand)
        side.addWidget(accent)
        side.addSpacing(26)

        self.stack = QStackedWidget()
        pages = (
            ("⌂   Dashboard", DashboardPage(settings, events)),
            ("▣   Overlay", OverlaySettingsPage(settings, events)),
            ("◎   OCR", OCRSettingsPage(settings, events)),
            ("⇄   Dịch thuật", TranslationSettingsPage(settings, events, database)),
            ("◷   Lịch sử", HistoryPage(settings, database, events)),
        )
        self.navigation: list[QPushButton] = []
        for index, (label, page) in enumerate(pages):
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(lambda checked=False, i=index: self._navigate(i))
            side.addWidget(button)
            self.navigation.append(button)
            self.stack.addWidget(page)
        self.navigation[0].setChecked(True)
        side.addStretch()

        privacy = QLabel("● Không quan sát màn hình")
        privacy.setObjectName("StatusGood")
        privacy.setWordWrap(True)
        side.addWidget(privacy)
        version = QLabel(f"Phiên bản {__version__} · MVP")
        version.setObjectName("PageSubtitle")
        side.addWidget(version)
        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)

        self.floating = FloatingController(events)
        events.notice.connect(self._show_notice)
        events.show_settings_requested.connect(self._show_overlay_settings)
        events.show_translation_settings_requested.connect(
            self._show_translation_settings
        )
        geometry = self.window_settings.value("main_geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def show_with_controller(self) -> None:
        self.show()
        screen = self.screen()
        if screen:
            area = screen.availableGeometry()
            self.floating.adjustSize()
            size = self.floating.sizeHint()
            self.floating.move(area.right() - size.width() - 28, area.bottom() - size.height() - 28)
        self.floating.show()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        exclude_window_from_capture(int(self.winId()))

    def _navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)

    def _show_overlay_settings(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.navigation[1].click()

    def _show_translation_settings(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.navigation[3].click()

    def _show_notice(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        # Disappear immediately; native Paddle inference cannot be interrupted
        # safely, so teardown may continue briefly in the background.
        self.hide()
        self.floating.hide()
        self.events.stop()
        if self.hotkey_manager is not None:
            self.hotkey_manager.close()
        if self.runtime_controller is not None:
            self.runtime_controller.shutdown()
        self.window_settings.setValue("main_geometry", self.saveGeometry())
        self.floating.close()
        event.accept()


