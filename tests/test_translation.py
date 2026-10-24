from __future__ import annotations

import httpx

from app.core.config import AppSettings
from app.core.models import TranslationResult
from app.database.db import Database
from app.translation.base_provider import (
    ProviderConfig,
    TranslationError,
    TranslationProvider,
)
from app.translation.deepl_provider import DeepLProvider
from app.translation.offline_provider import OfflineProvider
from app.translation.translation_service import TranslationService


class MockProvider(TranslationProvider):
    name = "deepl"

    def __init__(self):
        super().__init__(ProviderConfig("test", 3))
        self.calls = 0

    def translate_many(self, texts, source_language, target_language):
        self.calls += 1
        return [
            TranslationResult(text, f"VI:{text}", source_language, self.name, len(text))
            for text in texts
        ]

    def test_connection(self):
        return None


def test_translation_service_uses_cache(monkeypatch, tmp_path):
    settings = AppSettings(data_dir=tmp_path, cache_enabled=True)
    service = TranslationService(settings, Database(settings.database_path))
    provider = MockProvider()
    monkeypatch.setattr(service, "provider", lambda: provider)

    first = service.translate_many(["Hello"], "EN", "VI")
    second = service.translate_many(["Hello"], "EN", "VI")

    assert first[0].translated_text == "VI:Hello"
    assert second[0].from_cache
    assert provider.calls == 1


def test_bundled_offline_translation_needs_no_api_key():
    provider = OfflineProvider(ProviderConfig("", 3))

    result = provider.translate_many(["This is a book."], "EN", "VI")

    assert result[0].translated_text
    assert result[0].provider == "offline"
    assert result[0].billed_characters == 0


def test_offline_service_is_configured_without_secret(tmp_path):
    settings = AppSettings(data_dir=tmp_path, translation_provider="offline")
    service = TranslationService(settings, Database(settings.database_path))

    assert service.is_configured()
    assert service.provider().name == "offline"
    assert service.provider() is service.provider()


def test_deepl_network_error_is_retryable(monkeypatch):
    provider = DeepLProvider(ProviderConfig("key", 3))

    def fail(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "post", fail)
    try:
        provider.translate_many(["Hello"], "EN", "VI")
    except TranslationError as exc:
        assert exc.retryable
        assert "DeepL" in str(exc)
    else:
        raise AssertionError("Expected TranslationError")


def test_deepl_response_order_is_preserved(monkeypatch):
    provider = DeepLProvider(ProviderConfig("key", 3))
    request = httpx.Request("POST", "https://api.deepl.com/v2/translate")
    response = httpx.Response(
        200,
        request=request,
        json={
            "translations": [
                {"text": "Một", "detected_source_language": "EN"},
                {"text": "Hai", "detected_source_language": "EN"},
            ]
        },
    )
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)
    result = provider.translate_many(["One", "Two"], "EN", "VI")
    assert [item.translated_text for item in result] == ["Một", "Hai"]

