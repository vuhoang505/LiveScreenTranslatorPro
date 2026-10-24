from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import QObject, Signal, Slot


class RuntimeStatus(StrEnum):
    UNAVAILABLE = "unavailable"
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


class ApplicationEvents(QObject):
    """Typed event bus shared by the main and floating windows."""

    status_changed = Signal(str)
    notice = Signal(str, str)
    settings_saved = Signal()
    clear_overlay_requested = Signal()
    force_retranslate_requested = Signal()
    toggle_overlay_requested = Signal()
    show_settings_requested = Signal()
    show_translation_settings_requested = Signal()
    test_translation_requested = Signal()
    pipeline_status_changed = Signal(str, str)
    metrics_updated = Signal(int, float, int)
    history_changed = Signal()

    def __init__(self, engine_available: bool = False) -> None:
        super().__init__()
        self._engine_available = engine_available
        self._status = RuntimeStatus.STOPPED if engine_available else RuntimeStatus.UNAVAILABLE

    @property
    def status(self) -> RuntimeStatus:
        return self._status

    @property
    def engine_available(self) -> bool:
        return self._engine_available

    @Slot()
    def start(self) -> None:
        if not self._engine_available:
            self.notice.emit(
                "Pipeline chưa được bật",
                "Pipeline không khả dụng trong phiên này. Kiểm tra dependency và app.log.",
            )
            return
        self._set_status(RuntimeStatus.RUNNING)

    @Slot()
    def toggle_start_stop(self) -> None:
        if self._status in {RuntimeStatus.STOPPED, RuntimeStatus.UNAVAILABLE}:
            self.start()
        else:
            self.stop()

    @Slot()
    def stop(self) -> None:
        if self._engine_available:
            self._set_status(RuntimeStatus.STOPPED)

    @Slot()
    def toggle_pause(self) -> None:
        if not self._engine_available:
            self.start()
        elif self._status is RuntimeStatus.RUNNING:
            self._set_status(RuntimeStatus.PAUSED)
        elif self._status is RuntimeStatus.PAUSED:
            self._set_status(RuntimeStatus.RUNNING)

    def _set_status(self, status: RuntimeStatus) -> None:
        if status != self._status:
            self._status = status
            self.status_changed.emit(status.value)

    def set_status(self, status: RuntimeStatus) -> None:
        self._set_status(status)


