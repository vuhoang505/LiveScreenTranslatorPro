from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from app.core.models import BoundingBox


@dataclass(frozen=True, slots=True)
class ChangeAnalysis:
    should_process: bool
    changed: bool
    stable: bool
    changed_ratio: float
    hash_distance: int
    regions: tuple[BoundingBox, ...]


@dataclass(slots=True)
class _ScreenState:
    accepted_gray: np.ndarray | None = None
    accepted_hash: np.ndarray | None = None
    pending_gray: np.ndarray | None = None
    pending_hash: np.ndarray | None = None
    pending_since: float = 0.0


class ScreenChangeDetector:
    def __init__(
        self,
        threshold: float = 0.035,
        debounce_seconds: float = 0.65,
        pixel_threshold: int = 22,
        minimum_region_area: int = 160,
        analysis_width: int = 960,
    ) -> None:
        self.threshold = threshold
        self.debounce_seconds = debounce_seconds
        self.pixel_threshold = pixel_threshold
        self.minimum_region_area = minimum_region_area
        self.analysis_width = analysis_width
        self._states: dict[str, _ScreenState] = {}

    @staticmethod
    def perceptual_hash(gray: np.ndarray) -> np.ndarray:
        resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
        return resized[:, 1:] > resized[:, :-1]

    def analyze(
        self,
        screen_id: str,
        image: np.ndarray,
        *,
        now: float | None = None,
        force: bool = False,
    ) -> ChangeAnalysis:
        current_time = time.monotonic() if now is None else now
        gray, scale = self._prepare(image)
        image_hash = self.perceptual_hash(gray)
        state = self._states.setdefault(screen_id, _ScreenState())
        if (
            force
            or state.accepted_gray is None
            or state.accepted_gray.shape != gray.shape
        ):
            state.accepted_gray = gray
            state.accepted_hash = image_hash
            state.pending_gray = None
            return ChangeAnalysis(
                True,
                True,
                True,
                1.0,
                64,
                (BoundingBox(0, 0, image.shape[1], image.shape[0]),),
            )

        difference = cv2.absdiff(state.accepted_gray, gray)
        mask = difference >= self.pixel_threshold
        changed_ratio = float(np.count_nonzero(mask)) / float(mask.size)
        hash_distance = int(np.count_nonzero(state.accepted_hash != image_hash))
        meaningful = changed_ratio >= self.threshold or hash_distance >= 6
        if not meaningful:
            state.pending_gray = None
            state.pending_hash = None
            return ChangeAnalysis(False, False, True, changed_ratio, hash_distance, ())

        pending_matches = (
            state.pending_gray is not None
            and self._similar(state.pending_gray, gray) < self.threshold * 0.35
        )
        if not pending_matches:
            state.pending_gray = gray
            state.pending_hash = image_hash
            state.pending_since = current_time
            return ChangeAnalysis(
                False,
                True,
                False,
                changed_ratio,
                hash_distance,
                self._regions(mask, scale, image.shape[1], image.shape[0]),
            )
        if current_time - state.pending_since < self.debounce_seconds:
            return ChangeAnalysis(
                False,
                True,
                False,
                changed_ratio,
                hash_distance,
                self._regions(mask, scale, image.shape[1], image.shape[0]),
            )

        state.accepted_gray = gray
        state.accepted_hash = image_hash
        state.pending_gray = None
        state.pending_hash = None
        return ChangeAnalysis(
            True,
            True,
            True,
            changed_ratio,
            hash_distance,
            self._regions(mask, scale, image.shape[1], image.shape[0]),
        )

    def reset(self) -> None:
        self._states.clear()

    def _prepare(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        if gray.shape[1] <= self.analysis_width:
            return gray, 1.0
        scale = self.analysis_width / gray.shape[1]
        resized = cv2.resize(
            gray,
            (self.analysis_width, max(1, round(gray.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )
        return resized, scale

    def _similar(self, first: np.ndarray, second: np.ndarray) -> float:
        difference = cv2.absdiff(first, second)
        return float(np.count_nonzero(difference >= self.pixel_threshold)) / difference.size

    def _regions(
        self, mask: np.ndarray, scale: float, original_width: int, original_height: int
    ) -> tuple[BoundingBox, ...]:
        expanded = cv2.dilate(mask.astype(np.uint8) * 255, np.ones((7, 7), np.uint8))
        contours, _ = cv2.findContours(
            expanded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        regions: list[BoundingBox] = []
        inverse_scale = 1.0 / scale
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if width * height < self.minimum_region_area:
                continue
            left = max(0, round(x * inverse_scale))
            top = max(0, round(y * inverse_scale))
            right = min(original_width, round((x + width) * inverse_scale))
            bottom = min(original_height, round((y + height) * inverse_scale))
            regions.append(BoundingBox(left, top, right - left, bottom - top))
        regions.sort(key=lambda item: item.width * item.height, reverse=True)
        return tuple(regions[:24])

