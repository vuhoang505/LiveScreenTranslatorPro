from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import get_settings
from app.ocr.ocr_engine import LANGUAGE_NAMES, OCREngine


def model_names(language: str, model: str) -> tuple[str, str]:
    version = model.split("_")[0]
    size = "server" if model.endswith("_server") else "mobile"
    recognition = f"{version}_{size}_rec"
    if size == "mobile" and language in {"en", "korean"}:
        recognition = f"{language}_{version}_mobile_rec"
    return f"{version}_{size}_det", recognition


def model_status(model_directory: Path, language: str, model: str) -> dict[str, bool]:
    root = model_directory / "paddlex" / "official_models"
    return {
        name: (root / name / "inference.json").is_file()
        for name in model_names(language, model)
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage local PaddleOCR models")
    parser.add_argument("--language", choices=sorted(LANGUAGE_NAMES), default="en")
    parser.add_argument(
        "--model",
        choices=("PP-OCRv5_mobile", "PP-OCRv5_server"),
        default="PP-OCRv5_mobile",
    )
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)
    settings = get_settings()
    model_directory = settings.data_dir / "models"
    status = model_status(model_directory, args.language, args.model)
    if args.status:
        for name, installed in status.items():
            print(f"{name}: {'installed' if installed else 'missing'}")
        return 0 if all(status.values()) else 1
    engine = OCREngine(
        args.language,
        args.model,
        settings.ocr_confidence_threshold,
        settings.ocr_use_gpu,
        settings.ocr_cpu_threads,
        model_directory,
    )
    engine.initialize()
    print(f"OCR models ready in: {model_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

