from __future__ import annotations

from html import unescape

import httpx

from app.core.models import TranslationResult
from app.translation.base_provider import TranslationError, TranslationProvider


class GoogleProvider(TranslationProvider):
    name = "google"
    endpoint = "https://translation.googleapis.com/language/translate/v2"

    def translate_many(
        self,
        texts: list[str],
        source_language: str | None,
        target_language: str,
    ) -> list[TranslationResult]:
        body: dict[str, object] = {
            "q": texts,
            "target": target_language.lower(),
            "format": "text",
        }
        if source_language and source_language.lower() != "auto":
            body["source"] = source_language.lower()
        try:
            response = httpx.post(
                self.endpoint,
                params={"key": self.config.api_key},
                json=body,
                timeout=self.config.timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TranslationError(
                "Không thể kết nối Google Cloud Translation.", retryable=True
            ) from exc
        self._raise_for_response(response)
        translations = response.json().get("data", {}).get("translations", [])
        if len(translations) != len(texts):
            raise TranslationError("Google trả về số lượng kết quả không hợp lệ.")
        return [
            TranslationResult(
                source_text=source,
                translated_text=unescape(item["translatedText"]),
                detected_language=item.get("detectedSourceLanguage"),
                provider=self.name,
                billed_characters=len(source),
            )
            for source, item in zip(texts, translations, strict=True)
        ]

    def test_connection(self) -> None:
        try:
            response = httpx.get(
                f"{self.endpoint}/languages",
                params={"key": self.config.api_key, "target": "vi"},
                timeout=self.config.timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TranslationError(
                "Không thể kết nối Google Cloud Translation.", retryable=True
            ) from exc
        self._raise_for_response(response)

