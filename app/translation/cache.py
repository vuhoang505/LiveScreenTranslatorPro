from __future__ import annotations

import hashlib

from app.core.models import TranslationResult
from app.database.db import Database


class TranslationCache:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def make_key(
        text: str, provider: str, source_language: str | None, target_language: str
    ) -> str:
        normalized = " ".join(text.split())
        material = "\x1f".join(
            (provider, source_language or "auto", target_language, normalized)
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def get(
        self, text: str, provider: str, source_language: str | None, target_language: str
    ) -> TranslationResult | None:
        row = self.database.get_cache(
            self.make_key(text, provider, source_language, target_language)
        )
        if row is None:
            return None
        return TranslationResult(
            source_text=text,
            translated_text=row["translated_text"],
            detected_language=row["detected_language"],
            provider=row["provider"],
            billed_characters=0,
            from_cache=True,
        )

    def put(
        self,
        result: TranslationResult,
        source_language: str | None,
        target_language: str,
    ) -> None:
        self.database.put_cache(
            self.make_key(
                result.source_text, result.provider, source_language, target_language
            ),
            result.source_text,
            result.translated_text,
            result.detected_language,
            result.provider,
            source_language,
            target_language,
        )

