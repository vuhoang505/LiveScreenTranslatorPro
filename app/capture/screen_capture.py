from __future__ import annotations

import ctypes
import logging
import os
import threading

import mss
import numpy as np
import psutil
from PySide6.QtCore import QThread
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.core.models import BoundingBox, ScreenFrame

logger = logging.getLogger(__name__)


class ScreenCaptureError(RuntimeError):
    pass


class ScreenCaptureService:
    """Capture monitors into memory. No screenshot is written to disk."""

    def __init__(self) -> None:
        self._local = threading.local()
        self._backends: list[mss.mss] = []
        self._backends_lock = threading.Lock()
        self._mss_enabled = True

    def _backend(self) -> mss.mss:
        backend = getattr(self._local, "backend", None)
        if backend is None:
            backend = mss.mss()
            self._local.backend = backend
            with self._backends_lock:
                self._backends.append(backend)
        return backend

    def monitors(self) -> list[BoundingBox]:
        try:
            monitors = self._backend().monitors[1:]
        except mss.exception.ScreenShotError as exc:
            raise ScreenCaptureError(f"Không thể đọc danh sách màn hình: {exc}") from exc
        return [
            BoundingBox(item["left"], item["top"], item["width"], item["height"])
            for item in monitors
        ]

    def capture(self, monitor_index: int = 0) -> list[ScreenFrame]:
        """Capture all physical monitors for index 0, otherwise one 1-based monitor."""
        backend = self._backend()
        try:
            available = backend.monitors[1:]
        except mss.exception.ScreenShotError:
            available = []
            self._mss_enabled = False
        if not self._mss_enabled:
            return self._capture_with_qt(monitor_index, available)
        if not available:
            return self._capture_with_qt(monitor_index, available)
        if monitor_index < 0 or monitor_index > len(available):
            raise ScreenCaptureError(
                f"Màn hình {monitor_index} không tồn tại; hiện có {len(available)} màn hình."
            )
        selected = (
            list(enumerate(available, start=1))
            if monitor_index == 0
            else [(monitor_index, available[monitor_index - 1])]
        )
        frames: list[ScreenFrame] = []
        try:
            for index, monitor in selected:
                screenshot = backend.grab(monitor)
                bgra = np.asarray(screenshot)
                image = np.ascontiguousarray(bgra[:, :, :3])
                bounds = BoundingBox(
                    monitor["left"], monitor["top"], monitor["width"], monitor["height"]
                )
                frames.append(
                    ScreenFrame(
                        screen_id=f"monitor-{index}",
                        monitor_index=index,
                        image=image,
                        physical_bounds=bounds,
                    )
                )
        except mss.exception.ScreenShotError as exc:
            self._mss_enabled = False
            logger.warning("MSS capture failed; trying the Qt screen backend: %s", exc)
            try:
                return self._capture_with_qt(monitor_index, available)
            except ScreenCaptureError as fallback_exc:
                raise ScreenCaptureError(
                    f"Chụp màn hình thất bại (MSS: {exc}; Qt: {fallback_exc})"
                ) from exc
        return frames

    @staticmethod
    def _capture_with_qt(
        monitor_index: int, available: list[dict[str, int]]
    ) -> list[ScreenFrame]:
        """Fallback for systems where Windows GDI BitBlt is unavailable.

        QScreen/QPixmap must only be touched by the Qt GUI thread. The
        controller performs capture there and leaves OCR on its worker thread.
        """
        application = QApplication.instance()
        if application is None:
            raise ScreenCaptureError("Qt chưa khởi tạo nên không thể chụp dự phòng.")
        if QThread.currentThread() is not application.thread():
            raise ScreenCaptureError("Chụp dự phòng Qt phải chạy trên luồng giao diện.")

        screens = list(application.screens())
        if not screens:
            raise ScreenCaptureError("Qt không tìm thấy màn hình khả dụng.")
        if monitor_index < 0 or monitor_index > len(screens):
            raise ScreenCaptureError(
                f"Màn hình {monitor_index} không tồn tại; hiện có {len(screens)} màn hình."
            )
        selected = (
            list(enumerate(screens, start=1))
            if monitor_index == 0
            else [(monitor_index, screens[monitor_index - 1])]
        )
        frames: list[ScreenFrame] = []
        for index, screen in selected:
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                raise ScreenCaptureError(f"Qt không chụp được màn hình {index}.")
            image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            width = image.width()
            height = image.height()
            raw = np.frombuffer(
                image.bits(), dtype=np.uint8, count=image.sizeInBytes()
            ).reshape(height, image.bytesPerLine())
            rgba = raw[:, : width * 4].reshape(height, width, 4)
            bgr = np.ascontiguousarray(rgba[:, :, 2::-1])

            if index <= len(available):
                left = int(available[index - 1]["left"])
                top = int(available[index - 1]["top"])
            else:
                geometry = screen.geometry()
                ratio = float(screen.devicePixelRatio())
                left = round(geometry.x() * ratio)
                top = round(geometry.y() * ratio)
            frames.append(
                ScreenFrame(
                    screen_id=f"monitor-{index}",
                    monitor_index=index,
                    image=bgr,
                    physical_bounds=BoundingBox(left, top, width, height),
                )
            )
        return frames

    @staticmethod
    def foreground_process_name() -> str | None:
        if os.name != "nt":
            return None
        try:
            user32 = ctypes.windll.user32
            window = user32.GetForegroundWindow()
            if not window:
                return None
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
            return psutil.Process(pid.value).name().lower()
        except (AttributeError, OSError, psutil.Error):
            logger.debug("Unable to resolve foreground process", exc_info=True)
            return None

    def close(self) -> None:
        with self._backends_lock:
            backends = list(self._backends)
            self._backends.clear()
        for backend in backends:
            try:
                backend.close()
            except (AttributeError, OSError):
                logger.debug("Unable to close MSS backend", exc_info=True)
        self._local.backend = None

