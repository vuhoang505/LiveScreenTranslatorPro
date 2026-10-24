from __future__ import annotations

import shutil
from pathlib import Path

DEFAULT_OCR_MODELS = (
    "PP-OCRv5_mobile_det",
    "en_PP-OCRv5_mobile_rec",
)


def bundled_models_directory() -> Path:
    """Return the source/PyInstaller location of immutable bundled models."""
    return Path(__file__).resolve().parents[1] / "resources" / "models"


def bundled_translation_model_directory() -> Path:
    return bundled_models_directory() / "translate-en_vi-1_9"


def ensure_default_ocr_models(destination: Path) -> Path:
    """Seed the writable Paddle cache from the release without using a network."""
    target_root = destination / "paddlex" / "official_models"
    if all((target_root / name / "inference.json").is_file() for name in DEFAULT_OCR_MODELS):
        return destination

    source_root = bundled_models_directory() / "ocr" / "paddlex" / "official_models"
    missing = [
        name for name in DEFAULT_OCR_MODELS
        if not (source_root / name / "inference.json").is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "Bản phát hành thiếu model OCR tích hợp: " + ", ".join(missing)
        )

    target_root.mkdir(parents=True, exist_ok=True)
    for name in DEFAULT_OCR_MODELS:
        shutil.copytree(source_root / name, target_root / name, dirs_exist_ok=True)
    return destination
