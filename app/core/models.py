from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def union(self, other: BoundingBox) -> BoundingBox:
        left = min(self.x, other.x)
        top = min(self.y, other.y)
        right = max(self.right, other.right)
        bottom = max(self.bottom, other.bottom)
        return BoundingBox(left, top, right - left, bottom - top)


@dataclass(slots=True)
class ScreenFrame:
    screen_id: str
    monitor_index: int
    image: np.ndarray
    physical_bounds: BoundingBox
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class ScreenDescriptor:
    screen_id: str
    logical_bounds: BoundingBox


@dataclass(frozen=True, slots=True)
class OCRBlock:
    id: str
    text: str
    confidence: float
    bounding_box: BoundingBox
    polygon: tuple[tuple[int, int], ...]
    language: str
    paragraph_id: str
    screen_id: str


@dataclass(frozen=True, slots=True)
class TextParagraph:
    id: str
    text: str
    confidence: float
    bounding_box: BoundingBox
    block_ids: tuple[str, ...]
    screen_id: str


@dataclass(frozen=True, slots=True)
class TranslationResult:
    source_text: str
    translated_text: str
    detected_language: str | None
    provider: str
    billed_characters: int
    from_cache: bool = False


@dataclass(frozen=True, slots=True)
class OverlayBlock:
    id: str
    source_text: str
    translated_text: str
    bounding_box: BoundingBox
    screen_id: str
    background_color: str = "#10182B"

