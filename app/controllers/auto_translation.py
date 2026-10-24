from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, replace

import cv2
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication

from app.capture.change_detector import ScreenChangeDetector
from app.capture.screen_capture import ScreenCaptureError, ScreenCaptureService
from app.core.config import AppSettings
from app.core.events import ApplicationEvents, RuntimeStatus
from app.core.models import (
    BoundingBox,
    OCRBlock,
    OverlayBlock,
    ScreenDescriptor,
    ScreenFrame,
)
from app.database.db import Database
from app.ocr.ocr_engine import OCREngine
from app.ocr.text_layout import group_into_paragraphs
from app.overlay.coordinate_mapper import CoordinateMapper, sample_background_color
from app.overlay.overlay_window import TranslationOverlay
from app.translation.translation_service import TranslationService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineOutcome:
    blocks: tuple[OverlayBlock, ...]
    updated_screens: tuple[str, ...]
    elapsed_seconds: float
    ocr_segments: int
    billed_characters: int
    updated_regions: tuple[tuple[str, BoundingBox], ...] = ()
    stale: bool = False
    no_change: bool = False
    privacy_process: str | None = None


class _WorkerSignals(QObject):
    finished = Signal(int, object)
    failed = Signal(int, str)


class _PipelineWorker(QRunnable):
    def __init__(
        self,
        generation: int,
        force: bool,
        settings: AppSettings,
        descriptors: dict[str, ScreenDescriptor],
        session_id: int | None,
        frames: list[ScreenFrame],
        detector: ScreenChangeDetector,
        ocr: OCREngine,
        translation: TranslationService,
        cancelled: threading.Event,
    ) -> None:
        super().__init__()
        self.generation = generation
        self.force = force
        self.settings = settings
        self.descriptors = descriptors
        self.session_id = session_id
        self.frames = frames
        self.detector = detector
        self.ocr = ocr
        self.translation = translation
        self.cancelled = cancelled
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        started = time.perf_counter()
        try:
            frames = self.frames
            if self.cancelled.is_set():
                self._emit_cancelled(started)
                return
            changed_frames: list[tuple[ScreenFrame, tuple[BoundingBox, ...]]] = []
            for frame in frames:
                analysis = self.detector.analyze(
                    frame.screen_id, frame.image, force=self.force
                )
                if analysis.should_process:
                    changed_frames.append(
                        (frame, self._regions_for_ocr(frame, analysis.regions))
                    )
            if not changed_frames:
                self.signals.finished.emit(
                    self.generation,
                    PipelineOutcome(
                        (), (), time.perf_counter() - started, 0, 0, no_change=True
                    ),
                )
                return

            recognized = []
            for frame, regions in changed_frames:
                if self.cancelled.is_set():
                    self._emit_cancelled(started)
                    return
                ocr_blocks: list[OCRBlock] = []
                for region in regions:
                    crop = frame.image[region.y : region.bottom, region.x : region.right]
                    blocks = self.ocr.extract(crop, frame.screen_id)
                    ocr_blocks.extend(
                        self._offset_block(block, region.x, region.y) for block in blocks
                    )
                paragraphs = group_into_paragraphs(ocr_blocks)
                recognized.append((frame, paragraphs, regions))

            overlay_blocks: list[OverlayBlock] = []
            updated_regions: list[tuple[str, BoundingBox]] = []
            billed_characters = 0
            segment_count = 0
            for frame, paragraphs, regions in recognized:
                if self.cancelled.is_set():
                    self._emit_cancelled(started)
                    return
                segment_count += len(paragraphs)
                descriptor = self.descriptors.get(frame.screen_id)
                if descriptor is None:
                    logical_bounds = frame.physical_bounds
                else:
                    logical_bounds = descriptor.logical_bounds
                updated_regions.extend(
                    (
                        frame.screen_id,
                        CoordinateMapper.map_box(
                            region, frame.physical_bounds, logical_bounds
                        ),
                    )
                    for region in regions
                )
                if not paragraphs:
                    continue
                translations = self.translation.translate_many(
                    [paragraph.text for paragraph in paragraphs],
                    None
                    if self.settings.source_language.lower() == "auto"
                    else self.settings.source_language,
                    self.settings.target_language,
                    self.session_id,
                )
                billed_characters += sum(
                    result.billed_characters for result in translations
                )
                for paragraph, translation in zip(
                    paragraphs, translations, strict=True
                ):
                    logical_box = CoordinateMapper.map_box(
                        paragraph.bounding_box,
                        frame.physical_bounds,
                        logical_bounds,
                    )
                    overlay_blocks.append(
                        OverlayBlock(
                            id=paragraph.id,
                            source_text=paragraph.text,
                            translated_text=translation.translated_text,
                            bounding_box=logical_box,
                            screen_id=frame.screen_id,
                            background_color=sample_background_color(
                                frame.image, paragraph.bounding_box
                            ),
                        )
                    )

            if self.cancelled.is_set():
                self._emit_cancelled(started)
                return
            self.signals.finished.emit(
                self.generation,
                PipelineOutcome(
                    tuple(overlay_blocks),
                    tuple(frame.screen_id for frame, _regions in changed_frames),
                    time.perf_counter() - started,
                    segment_count,
                    billed_characters,
                    tuple(updated_regions),
                ),
            )
        except Exception as exc:
            logger.exception("Translation pipeline failed")
            self.signals.failed.emit(self.generation, str(exc))

    @staticmethod
    def _frame_hash(frame: ScreenFrame):
        gray = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY)
        thumbnail = cv2.resize(gray, (64, 36), interpolation=cv2.INTER_AREA)
        return ScreenChangeDetector.perceptual_hash(gray), thumbnail

    @staticmethod
    def _hash_distance(first, second) -> int:
        if first is None or second is None:
            return 64
        first_hash, first_thumbnail = first
        second_hash, second_thumbnail = second
        hash_distance = int((first_hash != second_hash).sum())
        pixel_ratio = float(
            (cv2.absdiff(first_thumbnail, second_thumbnail) >= 20).sum()
        ) / first_thumbnail.size
        if pixel_ratio >= 0.03:
            return 64
        # A taskbar clock/caret can flip several perceptual-hash bits while
        # changing far less than 0.1% of the screen. Do not keep throwing away
        # an otherwise valid OCR result for such tiny background activity.
        return hash_distance if pixel_ratio >= 0.001 else 0

    @classmethod
    def _frames_changed(cls, original_hashes, frames: list[ScreenFrame]) -> bool:
        return any(
            cls._hash_distance(
                original_hashes.get(frame.screen_id), cls._frame_hash(frame)
            )
            >= 8
            for frame in frames
        )

    def _emit_cancelled(self, started: float) -> None:
        self.signals.finished.emit(
            self.generation,
            PipelineOutcome((), (), time.perf_counter() - started, 0, 0, no_change=True),
        )

    @staticmethod
    def _regions_for_ocr(
        frame: ScreenFrame, regions: tuple[BoundingBox, ...]
    ) -> tuple[BoundingBox, ...]:
        """Expand and merge small changed areas; use full OCR for broad changes."""
        full = BoundingBox(0, 0, frame.image.shape[1], frame.image.shape[0])
        if not regions:
            return (full,)
        expanded: list[BoundingBox] = []
        margin = 48
        for region in regions:
            left = max(0, region.x - margin)
            top = max(0, region.y - margin)
            right = min(full.width, region.right + margin)
            bottom = min(full.height, region.bottom + margin)
            candidate = BoundingBox(left, top, right - left, bottom - top)
            merged = True
            while merged:
                merged = False
                for index, existing in enumerate(expanded):
                    if _boxes_overlap(candidate, existing, padding=12):
                        candidate = candidate.union(existing)
                        expanded.pop(index)
                        merged = True
                        break
            expanded.append(candidate)
        covered = sum(region.width * region.height for region in expanded)
        # Several separate Paddle predict() calls cost more than one resized
        # full-screen pass. Keep incremental OCR for one-to-three compact
        # areas (for example a subtitle), otherwise batch the work as one pass.
        if len(expanded) > 3 or covered >= full.width * full.height * 0.18:
            return (full,)
        return tuple(expanded)

    @staticmethod
    def _offset_block(block: OCRBlock, offset_x: int, offset_y: int) -> OCRBlock:
        if offset_x == 0 and offset_y == 0:
            return block
        box = replace(
            block.bounding_box,
            x=block.bounding_box.x + offset_x,
            y=block.bounding_box.y + offset_y,
        )
        polygon = tuple((x + offset_x, y + offset_y) for x, y in block.polygon)
        material = (
            f"{block.screen_id}\x1f{block.text}\x1f"
            f"{box.x},{box.y},{box.width},{box.height}"
        )
        block_id = hashlib.sha1(
            material.encode("utf-8"), usedforsecurity=False
        ).hexdigest()[:16]
        return replace(
            block,
            id=block_id,
            paragraph_id=block_id,
            bounding_box=box,
            polygon=polygon,
        )


def _boxes_overlap(first: BoundingBox, second: BoundingBox, padding: int = 0) -> bool:
    return not (
        first.right + padding < second.x
        or second.right + padding < first.x
        or first.bottom + padding < second.y
        or second.bottom + padding < first.y
    )


class _ConnectionTestWorker(QRunnable):
    def __init__(self, translation: TranslationService) -> None:
        super().__init__()
        self.translation = translation
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.translation.test_connection()
            self.signals.finished.emit(0, True)
        except Exception as exc:
            self.signals.failed.emit(0, str(exc))


class AutoTranslationController(QObject):
    def __init__(
        self,
        settings: AppSettings,
        events: ApplicationEvents,
        database: Database,
        capture: ScreenCaptureService,
        detector: ScreenChangeDetector,
        ocr: OCREngine,
        translation: TranslationService,
        overlay: TranslationOverlay,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.events = events
        self.database = database
        self.capture = capture
        self.detector = detector
        self.ocr = ocr
        self.translation = translation
        self.overlay = overlay
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        # Paddle predictors must be initialized and used on the same native
        # thread. Keep the single pipeline thread alive for the whole session.
        self.pool.setExpiryTimeout(-1)
        self.timer = QTimer(self)
        self.timer.setInterval(settings.capture_interval_ms)
        self.timer.timeout.connect(self._schedule)
        self._busy = False
        self._pending = False
        self._force_next = False
        self._generation = 0
        self._session_id: int | None = None
        self._segments = 0
        self._characters = 0
        self._blocks_by_screen: dict[str, list[OverlayBlock]] = {}
        self._active_cancel: threading.Event | None = None
        self._pipeline_workers: dict[int, _PipelineWorker] = {}
        self._connection_worker: _ConnectionTestWorker | None = None

        events.status_changed.connect(self._status_changed)
        events.clear_overlay_requested.connect(self.clear_overlay)
        events.force_retranslate_requested.connect(self.force_retranslate)
        events.toggle_overlay_requested.connect(self.overlay.toggle_visibility)
        events.test_translation_requested.connect(self.test_connection)
        events.settings_saved.connect(self._settings_saved)

    @Slot(str)
    def _status_changed(self, value: str) -> None:
        status = RuntimeStatus(value)
        if status is RuntimeStatus.RUNNING:
            if not self.translation.is_configured():
                self.events.notice.emit(
                    "Bộ dịch chưa sẵn sàng",
                    "Hãy chọn Offline trong Dịch thuật hoặc nhập API key cho provider online.",
                )
                self.events.show_translation_settings_requested.emit()
                self.events.set_status(RuntimeStatus.STOPPED)
                return
            if self._session_id is None:
                self._session_id = self.database.start_session()
            self.events.pipeline_status_changed.emit(
                "Đang theo dõi", "Chỉ OCR khi nội dung ổn định và thay đổi đủ lớn"
            )
            self.timer.start()
            self._force_next = True
            self._schedule()
        elif status is RuntimeStatus.PAUSED:
            self.timer.stop()
            if self._active_cancel is not None:
                self._active_cancel.set()
            self._generation += 1
            self.events.pipeline_status_changed.emit(
                "Đã tạm dừng", "Không chụp màn hình và không gửi dữ liệu"
            )
        elif status in {RuntimeStatus.STOPPED, RuntimeStatus.UNAVAILABLE}:
            self.timer.stop()
            if self._active_cancel is not None:
                self._active_cancel.set()
            self._generation += 1
            self._pending = False
            self._finish_session()
            self.events.pipeline_status_changed.emit(
                "Đã dừng", "Không quan sát màn hình"
            )

    @Slot()
    def _schedule(self) -> None:
        if self.events.status is not RuntimeStatus.RUNNING:
            return
        if self._busy:
            self._pending = True
            return
        foreground = self.capture.foreground_process_name()
        excluded = {name.lower() for name in self.settings.excluded_processes}
        if foreground and foreground in excluded:
            self.events.pipeline_status_changed.emit(
                "Đã bảo vệ riêng tư",
                f"Tạm bỏ qua ứng dụng bị loại trừ: {foreground}",
            )
            return
        self._busy = True
        self._pending = False
        self._generation += 1
        generation = self._generation
        # Paint our own status before taking the baseline screenshot. Without
        # this flush, the later repaint looks like a page change and can make
        # the app discard/restart every completed OCR cycle.
        self.events.pipeline_status_changed.emit(
            "Đang xử lý", "Đang đọc chữ và dịch phần màn hình vừa thay đổi…"
        )
        overlay_hidden = self.overlay.requires_hide_for_capture
        if overlay_hidden:
            self.overlay.hide_for_capture()
        QApplication.processEvents()
        try:
            # MSS/GDI is fastest when available. The service transparently
            # falls back to QScreen here; QScreen must run on the GUI thread.
            frames = self.capture.capture(self.settings.monitor_index)
        except ScreenCaptureError as exc:
            self._busy = False
            self.overlay.restore_after_capture()
            self.events.pipeline_status_changed.emit("Lỗi chụp màn hình", str(exc))
            self.events.notice.emit("Không thể chụp màn hình", str(exc))
            self.events.set_status(RuntimeStatus.STOPPED)
            return
        if overlay_hidden:
            # Capture is already copied into NumPy arrays; keep the previous
            # translation visible while OCR works in the background.
            self.overlay.restore_after_capture()
        self._active_cancel = threading.Event()
        worker = _PipelineWorker(
            generation,
            self._force_next,
            self.settings,
            self._screen_descriptors(),
            self._session_id,
            frames,
            self.detector,
            self.ocr,
            self.translation,
            self._active_cancel,
        )
        # PySide must not delete a Python QRunnable on the native worker
        # thread. The controller releases it on the GUI thread after delivery.
        worker.setAutoDelete(False)
        self._pipeline_workers[generation] = worker
        self._force_next = False
        worker.signals.finished.connect(self._worker_finished)
        worker.signals.failed.connect(self._worker_failed)
        self.pool.start(worker)

    @Slot(int, object)
    def _worker_finished(self, generation: int, outcome: PipelineOutcome) -> None:
        self._release_pipeline_worker(generation)
        self._busy = False
        self._active_cancel = None
        self.overlay.restore_after_capture()
        if generation != self._generation or self.events.status is not RuntimeStatus.RUNNING:
            self._continue_if_needed()
            return
        if outcome.privacy_process:
            self.events.pipeline_status_changed.emit(
                "Đã bảo vệ riêng tư",
                f"Tạm bỏ qua ứng dụng bị loại trừ: {outcome.privacy_process}",
            )
        elif outcome.stale:
            self.events.pipeline_status_changed.emit(
                "Trang đã thay đổi", "Bỏ kết quả cũ và ưu tiên trang hiện tại"
            )
            self._force_next = True
            QTimer.singleShot(50, self._schedule)
            return
        elif outcome.no_change:
            self.events.pipeline_status_changed.emit(
                "Đang theo dõi", "Không có thay đổi cần OCR"
            )
        else:
            regions_by_screen: dict[str, list[BoundingBox]] = {}
            for screen_id, region in outcome.updated_regions:
                regions_by_screen.setdefault(screen_id, []).append(region)
            for screen_id in outcome.updated_screens:
                new_blocks = [
                    block for block in outcome.blocks if block.screen_id == screen_id
                ]
                regions = regions_by_screen.get(screen_id)
                if not regions:
                    self._blocks_by_screen[screen_id] = new_blocks
                    continue
                retained = [
                    block
                    for block in self._blocks_by_screen.get(screen_id, [])
                    if not any(
                        _boxes_overlap(block.bounding_box, region) for region in regions
                    )
                ]
                self._blocks_by_screen[screen_id] = retained + new_blocks
            all_blocks = [
                block
                for screen_blocks in self._blocks_by_screen.values()
                for block in screen_blocks
            ]
            self.overlay.set_blocks(all_blocks)
            self._segments += outcome.ocr_segments
            self._characters += outcome.billed_characters
            self.events.metrics_updated.emit(
                self._segments, outcome.elapsed_seconds, self._characters
            )
            self.events.history_changed.emit()
            self.events.pipeline_status_changed.emit(
                "Đang theo dõi",
                f"Đã cập nhật {outcome.ocr_segments} đoạn trong "
                f"{outcome.elapsed_seconds:.2f} giây",
            )
        self._continue_if_needed()

    @Slot(int, str)
    def _worker_failed(self, generation: int, message: str) -> None:
        self._release_pipeline_worker(generation)
        self._busy = False
        self._active_cancel = None
        self.overlay.restore_after_capture()
        if generation != self._generation:
            return
        self.events.pipeline_status_changed.emit("Lỗi pipeline", message)
        self.events.notice.emit("Không thể dịch màn hình", message)
        self.events.set_status(RuntimeStatus.STOPPED)

    def _release_pipeline_worker(self, generation: int) -> None:
        worker = self._pipeline_workers.pop(generation, None)
        if worker is not None:
            worker.signals.deleteLater()

    def _continue_if_needed(self) -> None:
        if self._pending and self.events.status is RuntimeStatus.RUNNING:
            QTimer.singleShot(0, self._schedule)

    @Slot()
    def clear_overlay(self) -> None:
        self._blocks_by_screen.clear()
        self.overlay.clear()
        self.events.pipeline_status_changed.emit(
            "Đã xóa bản dịch", "Overlay đã được xóa khỏi màn hình"
        )

    @Slot()
    def force_retranslate(self) -> None:
        if self.events.status is not RuntimeStatus.RUNNING:
            self.events.notice.emit(
                "Chưa bắt đầu dịch", "Hãy bấm Bắt đầu dịch trước khi yêu cầu dịch lại."
            )
            return
        self.detector.reset()
        self._force_next = True
        if self._busy:
            if self._active_cancel is not None:
                self._active_cancel.set()
            self._generation += 1
            self._pending = True
        else:
            self._schedule()

    @Slot()
    def test_connection(self) -> None:
        if self._connection_worker is not None:
            self.events.notice.emit(
                "Đang kiểm tra", "Vui lòng chờ lần kiểm tra hiện tại hoàn tất."
            )
            return
        worker = _ConnectionTestWorker(self.translation)
        worker.setAutoDelete(False)
        self._connection_worker = worker
        worker.signals.finished.connect(self._connection_finished)
        worker.signals.failed.connect(self._connection_failed)
        self.pool.start(worker)

    @Slot(int, object)
    def _connection_finished(self, _generation: int, _result: object) -> None:
        worker = self._connection_worker
        self._connection_worker = None
        if worker is not None:
            worker.signals.deleteLater()
        self.events.notice.emit(
            "Kiểm tra thành công",
            "Bộ dịch offline đã sẵn sàng."
            if self.settings.translation_provider == "offline"
            else "Provider đã xác thực API key.",
        )

    @Slot(int, str)
    def _connection_failed(self, _generation: int, message: str) -> None:
        worker = self._connection_worker
        self._connection_worker = None
        if worker is not None:
            worker.signals.deleteLater()
        self.events.notice.emit("Kết nối thất bại", message)

    def _screen_descriptors(self) -> dict[str, ScreenDescriptor]:
        descriptors: dict[str, ScreenDescriptor] = {}
        for index, screen in enumerate(QApplication.screens(), start=1):
            geometry = screen.geometry()
            descriptors[f"monitor-{index}"] = ScreenDescriptor(
                f"monitor-{index}",
                BoundingBox(
                    geometry.x(), geometry.y(), geometry.width(), geometry.height()
                ),
            )
        return descriptors

    def _finish_session(self) -> None:
        if self._session_id is not None:
            self.database.end_session(
                self._session_id, self._segments, self._characters
            )
            self._session_id = None

    @Slot()
    def _settings_saved(self) -> None:
        self.timer.setInterval(self.settings.capture_interval_ms)
        self.detector.threshold = self.settings.change_threshold
        self.detector.debounce_seconds = self.settings.ocr_debounce_ms / 1000
        if (
            self.ocr.language != self.settings.ocr_language
            or self.ocr.model != self.settings.ocr_model
            or self.ocr.confidence_threshold
            != self.settings.ocr_confidence_threshold
            or self.ocr.use_gpu != self.settings.ocr_use_gpu
            or self.ocr.cpu_threads != self.settings.ocr_cpu_threads
        ):
            self.ocr = OCREngine(
                language=self.settings.ocr_language,
                model=self.settings.ocr_model,
                confidence_threshold=self.settings.ocr_confidence_threshold,
                use_gpu=self.settings.ocr_use_gpu,
                cpu_threads=self.settings.ocr_cpu_threads,
                model_directory=self.settings.data_dir / "models",
            )
        self.overlay.set_blocks(
            [
                block
                for screen_blocks in self._blocks_by_screen.values()
                for block in screen_blocks
            ]
        )

    def shutdown(self) -> None:
        self.timer.stop()
        self._generation += 1
        self.overlay.hide_for_capture()
        if self._active_cancel is not None:
            self._active_cancel.set()
        self._finish_session()
        # The pool uses an infinite expiry during normal operation so Paddle
        # stays on one native thread. Re-enable thread expiry before waiting,
        # otherwise an idle persistent pool can keep shutdown blocked forever.
        self.pool.setExpiryTimeout(0)
        self.pool.clear()
        # Never tear down Python/Paddle while native inference is still active.
        self.pool.waitForDone(-1)
        for worker in self._pipeline_workers.values():
            worker.signals.deleteLater()
        self._pipeline_workers.clear()
        if self._connection_worker is not None:
            self._connection_worker.signals.deleteLater()
            self._connection_worker = None
        self.capture.close()
        self.overlay.close()
        self.database.close()

