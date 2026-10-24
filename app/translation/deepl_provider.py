from __future__ import annotations

import httpx

from app.core.models import TranslationResult
from app.translation.base_provider import ProviderConfig, TranslationError, TranslationProvider


class DeepLProvider(TranslationProvider):
    name = "deepl"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        host = "api-free.deepl.com" if config.api_key.endswith(":fx") else "api.deepl.com"
        self.base_url = f"https://{host}/v2"

    def translate_many(
        self,
        texts: list[str],
        source_language: str | None,
        target_language: str,
    ) -> list[TranslationResult]:
        body: dict[str, object] = {
            "text": texts,
            "target_lang": target_language.upper(),
            "show_billed_characters": True,
            "preserve_formatting": True,
        }
        if source_language and source_language.lower() != "auto":
            body["source_lang"] = source_language.upper()
        try:
            response = httpx.post(
                f"{self.base_url}/translate",
                headers={
                    "Authorization": f"DeepL-Auth-Key {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=self.config.timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TranslationError(
                "Không thể kết nối DeepL.", retryable=True
            ) from exc
        self._raise_for_response(response)
        payload = response.json()
        translations = payload.get("translations", [])
        if len(translations) != len(texts):
            raise TranslationError("DeepL trả về số lượng kết quả không hợp lệ.")
        return [
            TranslationResult(
                source_text=source,
                translated_text=item["text"],
                detected_language=item.get("detected_source_language"),
                provider=self.name,
                billed_characters=int(item.get("billed_characters", len(source))),
            )
            for source, item in zip(texts, translations, strict=True)
        ]

    def test_connection(self) -> None:
        try:
            response = httpx.get(
                f"{self.base_url}/usage",
                headers={"Authorization": f"DeepL-Auth-Key {self.config.api_key}"},
                timeout=self.config.timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TranslationError("Không thể kết nối DeepL.", retryable=True) from exc
        self._raise_for_response(response)

