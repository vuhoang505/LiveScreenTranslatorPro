from __future__ import annotations

import json

from pydantic import SecretStr

from app.core.config import AppSettings, _load_persisted


def test_settings_save_excludes_secrets(tmp_path):
    settings = AppSettings(
        data_dir=tmp_path,
        deepl_api_key=SecretStr("do-not-write-me"),
        overlay_font_size=18,
    )

    settings.save()

    payload = json.loads(settings.settings_file.read_text(encoding="utf-8"))
    assert payload["overlay_font_size"] == 18
    assert "deepl_api_key" not in payload
    assert "google_api_key" not in payload
    assert "do-not-write-me" not in settings.settings_file.read_text(encoding="utf-8")


def test_numeric_settings_are_validated():
    settings = AppSettings(capture_interval_ms=100, overlay_opacity=0.2)
    assert settings.capture_interval_ms == 100
    assert settings.overlay_opacity == 0.2


def test_offline_is_the_zero_configuration_default():
    assert AppSettings().translation_provider == "offline"


def test_old_settings_migrate_to_offline_once(monkeypatch, tmp_path):
    monkeypatch.delenv("LST_TRANSLATION_PROVIDER", raising=False)
    settings = AppSettings(data_dir=tmp_path)
    settings.settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings.settings_file.write_text(
        json.dumps({"translation_provider": "deepl"}), encoding="utf-8"
    )

    loaded = _load_persisted(settings)

    assert loaded.translation_provider == "offline"
    assert loaded.settings_schema_version == 3
    assert loaded.capture_interval_ms == 350
    assert loaded.ocr_debounce_ms == 350

