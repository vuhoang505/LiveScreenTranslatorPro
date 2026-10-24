from __future__ import annotations

import threading
import time
from collections import deque

from app.core.config import AppSettings
from app.core.models import TranslationResult
from app.database.db import Database
from app.translation.base_provider import ProviderConfig, TranslationError, TranslationProvider
from app.translation.cache import TranslationCache
from app.translation.deepl_provider import DeepLProvider
from app.translation.google_provider import GoogleProvider
from app.translation.offline_provider import OfflineProvider
from app.translation.secrets import SecretStore, SecretStoreError


class TranslationService:
    def __init__(
        self,
        settings: AppSettings,
        database: Database,
        secret_store: SecretStore | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.cache = TranslationCache(database)
        self.secret_store = secret_store or SecretStore()
        self._request_times: deque[float] = deque()
        self._rate_lock = threading.Lock()
        self._provider_lock = threading.RLock()
        self._provider_instance: TranslationProvider | None = None
        self._provider_signature: tuple[str, str, float] | None = None

    def _api_key(self, provider: str) -> str | None:
        environment_secret = (
            self.settings.deepl_api_key
            if provider == "deepl"
            else self.settings.google_api_key
        )
        if environment_secret is not None:
            return environment_secret.get_secret_value()
        try:
            return self.secret_store.get(provider)
        except SecretStoreError:
            return None

    def is_configured(self) -> bool:
        if self.settings.translation_provider == "offline":
            return True
        return bool(self._api_key(self.settings.translation_provider))

    def provider(self) -> TranslationProvider:
        provider_name = self.settings.translation_provider
        api_key = "" if provider_name == "offline" else self._api_key(provider_name)
        if provider_name != "offline" and not api_key:
            raise TranslationError(
                f"Chưa có API key cho {provider_name}. Hãy mở Cài đặt Dịch thuật."
            )
        signature = (
            provider_name,
            api_key or "",
            self.settings.request_timeout_seconds,
        )
        with self._provider_lock:
            if (
                self._provider_instance is not None
                and self._provider_signature == signature
            ):
                return self._provider_instance

            config = ProviderConfig(api_key or "", self.settings.request_timeout_seconds)
            if provider_name == "offline":
                provider: TranslationProvider = OfflineProvider(config)
            elif provider_name == "deepl":
                provider = DeepLProvider(config)
            elif provider_name == "google":
                provider = GoogleProvider(config)
            else:
                raise TranslationError(f"Provider không được hỗ trợ: {provider_name}")
            self._provider_instance = provider
            self._provider_signature = signature
            return provider

    def warm_up(self) -> None:
        """Load local model files before the first live translation."""
        provider = self.provider()
        if isinstance(provider, OfflineProvider):
            provider.initialize()

    def test_connection(self) -> None:
        self.provider().test_connection()

    def translate_many(
        self,
        texts: list[str],
        source_language: str | None,
        target_language: str,
        session_id: int | None = None,
    ) -> list[TranslationResult]:
        if not texts:
            return []
        provider = self.provider()
        results: list[TranslationResult | None] = [None] * len(texts)
        missing_texts: list[str] = []
        missing_indexes: dict[str, list[int]] = {}
        for index, text in enumerate(texts):
            cached = (
                self.cache.get(text, provider.name, source_language, target_language)
                if self.settings.cache_enabled
                else None
            )
            if cached is None:
                if text not in missing_indexes:
                    missing_texts.append(text)
                    missing_indexes[text] = []
                missing_indexes[text].append(index)
            else:
                results[index] = cached

        if missing_texts:
            translated: list[TranslationResult] = []
            for batch in self._batches(missing_texts):
                if provider.name != "offline":
                    self._rate_limit()
                translated.extend(
                    self._with_retry(
                        lambda batch=batch: provider.translate_many(
                            batch, source_language, target_language
                        )
                    )
                )
            for result in translated:
                for index in missing_indexes[result.source_text]:
                    results[index] = result
                if self.settings.cache_enabled:
                    self.cache.put(result, source_language, target_language)
                if self.settings.history_enabled:
                    self.database.add_history(
                        session_id,
                        result.source_text,
                        result.translated_text,
                        result.detected_language or source_language,
                        target_language,
                        result.provider,
                    )
            self.database.add_usage(
                provider.name, sum(result.billed_characters for result in translated)
            )
        return [result for result in results if result is not None]

    @staticmethod
    def _batches(
        texts: list[str], max_items: int = 40, max_characters: int = 80_000
    ):
        batch: list[str] = []
        characters = 0
        for text in texts:
            if batch and (
                len(batch) >= max_items or characters + len(text) > max_characters
            ):
                yield batch
                batch = []
                characters = 0
            batch.append(text)
            characters += len(text)
        if batch:
            yield batch

    def _rate_limit(self) -> None:
        limit = self.settings.max_requests_per_minute
        with self._rate_lock:
            now = time.monotonic()
            while self._request_times and now - self._request_times[0] >= 60:
                self._request_times.popleft()
            if len(self._request_times) >= limit:
                delay = 60 - (now - self._request_times[0])
                if delay > 0:
                    time.sleep(delay)
            self._request_times.append(time.monotonic())

    @staticmethod
    def _with_retry(operation, attempts: int = 3):
        delay = 0.75
        for attempt in range(attempts):
            try:
                return operation()
            except TranslationError as exc:
                if not exc.retryable or attempt == attempts - 1:
                    raise
                time.sleep(exc.retry_after if exc.retry_after is not None else delay)
                delay *= 2
        raise AssertionError("unreachable")

