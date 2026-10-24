from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "LiveScreenTranslatorPro"


class AppSettings(BaseSettings):
    """Validated non-secret preferences plus environment-only provider secrets."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LST_",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )

    app_name: str = "LiveScreen Translator Pro"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    data_dir: Path = Field(default_factory=_default_data_dir)

    source_language: str = "auto"
    target_language: str = "VI"
    settings_schema_version: int = 3
    translation_provider: Literal["offline", "deepl", "google"] = "offline"
    request_timeout_seconds: float = Field(default=15.0, ge=3.0, le=120.0)
    max_requests_per_minute: int = Field(default=30, ge=1, le=1000)
    max_concurrent_tasks: int = Field(default=1, ge=1, le=4)
    cache_enabled: bool = True
    history_enabled: bool = True
    monitor_index: int = Field(default=0, ge=0, le=32)
    excluded_processes: list[str] = Field(
        default_factory=lambda: ["1password.exe", "bitwarden.exe", "keepass.exe"]
    )

    ocr_language: str = "en"
    ocr_model: str = "PP-OCRv5_mobile"
    ocr_confidence_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    change_threshold: float = Field(default=0.035, ge=0.001, le=1.0)
    capture_interval_ms: int = Field(default=350, ge=100, le=10_000)
    ocr_debounce_ms: int = Field(default=350, ge=100, le=10_000)
    ocr_cpu_threads: int = Field(default=4, ge=1, le=32)
    ocr_use_gpu: bool = False

    overlay_font_family: str = "Segoe UI"
    overlay_font_size: int = Field(default=16, ge=8, le=48)
    overlay_opacity: float = Field(default=0.90, ge=0.2, le=1.0)
    overlay_background: str = "#10182B"
    overlay_text_color: str = "#F2F7FF"
    overlay_line_spacing: float = Field(default=1.15, ge=0.8, le=2.0)
    overlay_cover_source: bool = True

    hotkey_toggle: str = "Ctrl+Alt+T"
    hotkey_pause: str = "Ctrl+Alt+P"
    hotkey_retranslate: str = "Ctrl+Alt+R"
    hotkey_overlay: str = "Ctrl+Alt+H"

    deepl_api_key: SecretStr | None = Field(default=None, exclude=True)
    google_api_key: SecretStr | None = Field(default=None, exclude=True)

    @property
    def settings_file(self) -> Path:
        return self.data_dir / "settings.json"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "livescreen.db"

    def save(self) -> None:
        """Persist only non-secret preferences with an atomic replace."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = self.model_dump(
            mode="json",
            exclude={"deepl_api_key", "google_api_key", "data_dir", "app_name"},
        )
        temporary = self.settings_file.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.settings_file)


def _load_persisted(settings: AppSettings) -> AppSettings:
    path = settings.settings_file
    if not path.exists():
        return settings
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        allowed = set(AppSettings.model_fields) - {
            "deepl_api_key",
            "google_api_key",
            "data_dir",
            "app_name",
        }
        updates = {key: value for key, value in values.items() if key in allowed}
        # Version 2 makes the bundled offline engine the zero-configuration
        # default. Migrate older settings once, unless an environment variable
        # explicitly selects a remote provider.
        schema_version = int(values.get("settings_schema_version", 1))
        if (
            schema_version < 2
            and "LST_TRANSLATION_PROVIDER" not in os.environ
        ):
            updates["translation_provider"] = "offline"
        if schema_version < 3:
            if values.get("capture_interval_ms", 750) == 750:
                updates["capture_interval_ms"] = 350
            if values.get("ocr_debounce_ms", 650) == 650:
                updates["ocr_debounce_ms"] = 350
            updates["settings_schema_version"] = 3
        values = settings.model_dump()
        values.update(updates)
        return AppSettings.model_validate(values)
    except (OSError, ValueError, TypeError):
        return settings


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return _load_persisted(AppSettings())

