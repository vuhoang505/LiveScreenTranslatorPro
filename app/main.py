from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app import __version__
from app.capture.change_detector import ScreenChangeDetector
from app.capture.screen_capture import ScreenCaptureService
from app.controllers.auto_translation import AutoTranslationController
from app.core.config import get_settings
from app.core.diagnostics import run_self_test
from app.core.events import ApplicationEvents
from app.core.hotkeys import GlobalHotkeyManager
from app.core.logging_config import configure_logging
from app.database.db import Database
from app.ocr.ocr_engine import OCREngine
from app.overlay.overlay_window import TranslationOverlay
from app.translation.translation_service import TranslationService
from app.ui.main_window import MainWindow
from app.ui.styles import APP_STYLE


def build_application(argv: list[str] | None = None) -> tuple[QApplication, MainWindow]:
    settings = get_settings()
    configure_logging(settings.log_dir, settings.log_level)
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(settings.app_name)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("LiveScreenTranslator")
    app.setQuitOnLastWindowClosed(True)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    icon_path = Path(__file__).parent / "resources" / "icons" / "app-icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    database = Database(settings.database_path)
    events = ApplicationEvents(engine_available=True)
    window = MainWindow(settings, events, database)
    capture = ScreenCaptureService()
    detector = ScreenChangeDetector(
        threshold=settings.change_threshold,
        debounce_seconds=settings.ocr_debounce_ms / 1000,
    )
    ocr = OCREngine(
        language=settings.ocr_language,
        model=settings.ocr_model,
        confidence_threshold=settings.ocr_confidence_threshold,
        use_gpu=settings.ocr_use_gpu,
        cpu_threads=settings.ocr_cpu_threads,
        model_directory=settings.data_dir / "models",
    )
    translation = TranslationService(settings, database)
    overlay = TranslationOverlay(settings)
    window.runtime_controller = AutoTranslationController(
        settings,
        events,
        database,
        capture,
        detector,
        ocr,
        translation,
        overlay,
    )
    window.hotkey_manager = GlobalHotkeyManager(app, settings, events)
    return app, window


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in arguments:
        index = arguments.index("--self-test")
        if index + 1 >= len(arguments):
            return 2
        return run_self_test(Path(arguments[index + 1]))
    try:
        app, window = build_application([sys.argv[0], *arguments])
        window.show_with_controller()
        return app.exec()
    except Exception as exc:  # pragma: no cover - last-resort GUI reporting
        logging.getLogger(__name__).exception("Fatal startup error")
        existing = QApplication.instance()
        if existing is None:
            existing = QApplication(sys.argv)
        QMessageBox.critical(None, "LiveScreen Translator Pro", f"Không thể khởi động:\n{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

