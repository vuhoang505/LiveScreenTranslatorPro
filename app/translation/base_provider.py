from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.models import TranslationResult


class TranslationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    api_key: str
    timeout_seconds: float


class TranslationProvider(ABC):
    name: str

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    def translate_many(
        self,
        texts: list[str],
        source_language: str | None,
        target_language: str,
    ) -> list[TranslationResult]:
        raise NotImplementedError

    @abstractmethod
    def test_connection(self) -> None:
        raise NotImplementedError

    @staticmethod
    def _raise_for_response(response: httpx.Response) -> None:
        if response.is_success:
            return
        retry_after: float | None = None
        raw_retry_after = response.headers.get("Retry-After")
        if raw_retry_after:
            try:
                retry_after = float(raw_retry_after)
            except ValueError:
                retry_after = None
        retryable = response.status_code in {408, 429, 500, 502, 503, 504, 529}
        messages = {
            401: "API key không hợp lệ.",
            403: "API key không có quyền dùng dịch vụ.",
            429: "Provider đang giới hạn tần suất yêu cầu.",
            456: "Đã hết hạn mức dịch của tài khoản.",
        }
        raise TranslationError(
            messages.get(response.status_code, f"Provider trả về HTTP {response.status_code}."),
            retryable=retryable,
            status_code=response.status_code,
            retry_after=retry_after,
        )

