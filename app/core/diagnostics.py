from __future__ import annotations

import json
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PySide6.QtWidgets import QApplication

from app.capture.screen_capture import ScreenCaptureService
from app.core.config import get_settings
from app.core.resources import bundled_translation_model_directory
from app.ocr.ocr_engine import OCREngine
from app.translation.base_provider import ProviderConfig
from app.translation.offline_provider import OfflineProvider
from app.translation.secrets import SecretStore


def run_self_test(report_path: Path) -> int:
    """Exercise lazy-loaded packaged components without calling a provider API."""
    report: dict[str, Any] = {
        "ok": False,
        "platform": platform.platform(),
        "checks": {},
    }
    capture: ScreenCaptureService | None = None
    diagnostic_application: QApplication | None = None
    try:
        import paddle
        from win32ctypes.pywin32 import pywintypes, win32cred

        report["checks"]["packages"] = {
            "paddle": paddle.__version__,
            "paddleocr": version("paddleocr"),
            "ctranslate2": version("ctranslate2"),
            "sentencepiece": version("sentencepiece"),
            "win32_credential_api": bool(win32cred and pywintypes),
        }

        offline = OfflineProvider(
            ProviderConfig("", 15), bundled_translation_model_directory()
        )
        translated = offline.translate_many(["Hello, how are you?"], "EN", "VI")
        if not translated or not translated[0].translated_text:
            raise RuntimeError("Bundled offline translator returned no text")
        report["checks"]["offline_translation"] = {
            "source": "EN",
            "target": "VI",
            "model": "translate-en_vi-1_9",
            "output_characters": len(translated[0].translated_text),
        }

        # Read a deliberately unused key. This verifies the packaged Windows
        # Credential Manager backend without creating or changing credentials.
        SecretStore().get("__packaged_self_test__")
        report["checks"]["credential_manager"] = True

        diagnostic_application = QApplication.instance() or QApplication(
            ["LiveScreenTranslatorPro-self-test"]
        )
        capture = ScreenCaptureService()
        frames = capture.capture(1)
        frame = frames[0]
        report["checks"]["capture"] = {
            "screens": len(frames),
            "width": frame.image.shape[1],
            "height": frame.image.shape[0],
        }

        # Synthetic content keeps the OCR check deterministic and ensures no
        # captured screen text is persisted in the diagnostic report.
        sample = np.full((220, 900, 3), 255, dtype=np.uint8)
        cv2.putText(
            sample,
            "Live Screen 2026",
            (35, 135),
            cv2.FONT_HERSHEY_SIMPLEX,
            2.0,
            (0, 0, 0),
            4,
            cv2.LINE_AA,
        )
        settings = get_settings()
        ocr = OCREngine(
            language="en",
            model="PP-OCRv5_mobile",
            confidence_threshold=0.40,
            use_gpu=False,
            cpu_threads=settings.ocr_cpu_threads,
            model_directory=settings.data_dir / "models",
        )
        blocks = ocr.extract(sample, "diagnostic")
        if not blocks:
            raise RuntimeError("PaddleOCR did not recognize the synthetic sample")
        report["checks"]["ocr"] = {
            "recognized_blocks": len(blocks),
            "used_bundled_models": True,
            "mean_confidence": round(
                sum(block.confidence for block in blocks) / len(blocks), 4
            ),
        }
        report["ok"] = True
    except Exception as exc:  # diagnostics must always leave a readable report
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if capture is not None:
            capture.close()
        if diagnostic_application is not None:
            diagnostic_application.quit()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0 if report["ok"] else 1
