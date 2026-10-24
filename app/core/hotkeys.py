from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject
from PySide6.QtWidgets import QApplication

from app.core.config import AppSettings
from app.core.events import ApplicationEvents

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000


class GlobalHotkeyManager(QObject, QAbstractNativeEventFilter):
    """Register configurable Windows hotkeys and report conflicts clearly."""

    def __init__(
        self, app: QApplication, settings: AppSettings, events: ApplicationEvents
    ) -> None:
        QObject.__init__(self)
        QAbstractNativeEventFilter.__init__(self)
        self.app = app
        self.settings = settings
        self.events = events
        self._callbacks = {
            0x5101: events.toggle_start_stop,
            0x5102: events.toggle_pause,
            0x5103: events.force_retranslate_requested.emit,
            0x5104: events.toggle_overlay_requested.emit,
        }
        self._registered: list[int] = []
        app.installNativeEventFilter(self)
        if os.name == "nt":
            self._register_all()

    def _register_all(self) -> None:
        hotkeys = (
            (0x5101, self.settings.hotkey_toggle),
            (0x5102, self.settings.hotkey_pause),
            (0x5103, self.settings.hotkey_retranslate),
            (0x5104, self.settings.hotkey_overlay),
        )
        for identifier, shortcut in hotkeys:
            try:
                modifiers, virtual_key = self._parse(shortcut)
            except ValueError as exc:
                self.events.notice.emit("Phím tắt không hợp lệ", str(exc))
                continue
            success = ctypes.windll.user32.RegisterHotKey(
                None, identifier, modifiers | MOD_NOREPEAT, virtual_key
            )
            if success:
                self._registered.append(identifier)
            else:
                self.events.notice.emit(
                    "Xung đột phím tắt",
                    f"Không thể đăng ký {shortcut}; có thể ứng dụng khác đang sử dụng.",
                )

    @staticmethod
    def _parse(shortcut: str) -> tuple[int, int]:
        parts = [part.strip().upper() for part in shortcut.split("+") if part.strip()]
        if not parts:
            raise ValueError(f"Phím tắt rỗng: {shortcut!r}")
        modifier_map = {
            "CTRL": MOD_CONTROL,
            "CONTROL": MOD_CONTROL,
            "ALT": MOD_ALT,
            "SHIFT": MOD_SHIFT,
            "WIN": MOD_WIN,
        }
        modifiers = 0
        for part in parts[:-1]:
            if part not in modifier_map:
                raise ValueError(f"Modifier không hỗ trợ trong '{shortcut}': {part}")
            modifiers |= modifier_map[part]
        key = parts[-1]
        if len(key) == 1 and key.isalnum():
            virtual_key = ord(key)
        elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
            virtual_key = 0x70 + int(key[1:]) - 1
        else:
            raise ValueError(f"Phím chính không hỗ trợ: {key}")
        return modifiers, virtual_key

    def nativeEventFilter(self, event_type, message):  # noqa: N802
        if os.name != "nt" or event_type not in {b"windows_generic_MSG", b"windows_dispatcher_MSG"}:
            return False, 0
        try:
            native_message = wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError):
            return False, 0
        if native_message.message == WM_HOTKEY:
            callback = self._callbacks.get(int(native_message.wParam))
            if callback is not None:
                callback()
                return True, 0
        return False, 0

    def close(self) -> None:
        if os.name == "nt":
            for identifier in self._registered:
                ctypes.windll.user32.UnregisterHotKey(None, identifier)
        self._registered.clear()
        self.app.removeNativeEventFilter(self)

