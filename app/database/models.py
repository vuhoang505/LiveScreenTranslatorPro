from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HistoryRecord:
    id: int
    source_text: str
    translated_text: str
    source_language: str | None
    target_language: str
    provider: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ApiUsageRecord:
    provider: str
    character_count: int
    request_count: int

