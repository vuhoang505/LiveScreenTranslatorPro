from __future__ import annotations

import ctypes
import os

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QApplication, QWidget

from app.core.config import AppSettings
from app.core.models import OverlayBlock
from app.overlay.text_renderer import fitted_font


def exclude_window_from_capture(window_id: int) -> bool:
    if os.name != "nt":
        return False
    try:
        result = ctypes.windll.user32.SetWindowDisplayAffinity(window_id, 0x00000011)
        return bool(result)
    except (AttributeError, OSError):
        return False


class _OverlayWindow(QWidget):
    def __init__(self, settings: AppSettings, screen_id: str) -> None:
        super().__init__()
        self.settings = settings
        self.screen_id = screen_id
        self.blocks: list[OverlayBlock] = []
        self.capture_excluded = False
        self.setWindowTitle(f"LiveScreen Overlay {screen_id}")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.capture_excluded = self._exclude_from_capture()

    def _exclude_from_capture(self) -> bool:
        return exclude_window_from_capture(int(self.winId()))

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        origin = self.geometry().topLeft()
        for block in self.blocks:
            box = block.bounding_box
            rect = QRect(
                box.x - origin.x(), box.y - origin.y(), box.width, box.height
            ).adjusted(-2, -2, 2, 2)
            rect = rect.intersected(self.rect())
            if rect.isEmpty():
                continue
            background = QColor(
                block.background_color
                if self.settings.overlay_cover_source
                else self.settings.overlay_background
            )
            opacity = self.settings.overlay_opacity
            if not self.settings.overlay_cover_source:
                opacity = min(opacity, 0.72)
            background.setAlpha(round(opacity * 255))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(rect, 3, 3)

            text_rect = rect.adjusted(4, 2, -4, -2)
            painter.setFont(
                fitted_font(
                    block.translated_text,
                    text_rect,
                    self.settings.overlay_font_family,
                    self.settings.overlay_font_size,
                )
            )
            painter.setPen(QColor(self.settings.overlay_text_color))
            painter.drawText(
                text_rect,
                int(
                    Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignVCenter
                    | Qt.TextFlag.TextWordWrap
                ),
                block.translated_text,
            )


class TranslationOverlay:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._windows: dict[str, _OverlayWindow] = {}
        self._last_blocks: list[OverlayBlock] = []
        self._hidden_for_capture = False
        self._user_hidden = False
        self.refresh_screens()

    def refresh_screens(self) -> None:
        current_ids: set[str] = set()
        for index, screen in enumerate(QApplication.screens(), start=1):
            screen_id = f"monitor-{index}"
            current_ids.add(screen_id)
            window = self._windows.get(screen_id)
            if window is None:
                window = _OverlayWindow(self.settings, screen_id)
                self._windows[screen_id] = window
            window.setGeometry(screen.geometry())
        for screen_id in set(self._windows) - current_ids:
            self._windows.pop(screen_id).close()

    @property
    def requires_hide_for_capture(self) -> bool:
        # SetWindowDisplayAffinity is not honored by every capture backend.
        # Always hide visible translated text for the few milliseconds needed
        # to capture so OCR never recursively reads its own overlay.
        return any(window.isVisible() for window in self._windows.values())

    def set_blocks(self, blocks: list[OverlayBlock]) -> None:
        self._last_blocks = blocks
        self.refresh_screens()
        for screen_id, window in self._windows.items():
            window.blocks = [block for block in blocks if block.screen_id == screen_id]
            if window.blocks and not self._hidden_for_capture and not self._user_hidden:
                window.show()
                window.raise_()
                window.update()
            elif not window.blocks:
                window.hide()

    def clear(self) -> None:
        self._last_blocks = []
        for window in self._windows.values():
            window.blocks = []
            window.hide()

    def hide_for_capture(self) -> None:
        self._hidden_for_capture = True
        for window in self._windows.values():
            window.hide()

    def restore_after_capture(self) -> None:
        self._hidden_for_capture = False
        if self._last_blocks:
            self.set_blocks(self._last_blocks)

    def toggle_visibility(self) -> None:
        self._user_hidden = not self._user_hidden
        if self._user_hidden:
            for window in self._windows.values():
                window.hide()
        elif self._last_blocks:
            self.set_blocks(self._last_blocks)

    def close(self) -> None:
        for window in self._windows.values():
            window.close()
        self._windows.clear()

