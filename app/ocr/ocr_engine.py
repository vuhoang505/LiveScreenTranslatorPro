from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from app.core.models import BoundingBox, OCRBlock
from app.core.resources import ensure_default_ocr_models

logger = logging.getLogger(__name__)


class OCREngineError(RuntimeError):
    pass


LANGUAGE_NAMES = {
    "en": "English",
    "ch": "Chinese",
    "japan": "Japanese",
    "korean": "Korean",
}


class OCREngine:
    def __init__(
        self,
        language: str = "en",
        model: str = "PP-OCRv5_mobile",
        confidence_threshold: float = 0.65,
        use_gpu: bool = False,
        cpu_threads: int = 4,
        model_directory: Path | None = None,
    ) -> None:
        if language not in LANGUAGE_NAMES:
            supported = ", ".join(LANGUAGE_NAMES)
            raise OCREngineError(
                f"Ngôn ngữ OCR '{language}' chưa được cấu hình. Hỗ trợ: {supported}."
            )
        if not model.startswith(("PP-OCRv3", "PP-OCRv4", "PP-OCRv5", "PP-OCRv6")):
            raise OCREngineError(f"Model OCR không được hỗ trợ: {model}")
        if model == "PP-OCRv5_server" and language == "korean":
            raise OCREngineError(
                "PP-OCRv5_server_rec không hỗ trợ Korean. "
                "Hãy chọn PP-OCRv5_mobile với ngôn ngữ Korean."
            )
        self.language = language
        self.model = model
        self.confidence_threshold = confidence_threshold
        self.use_gpu = use_gpu
        self.cpu_threads = cpu_threads
        self.model_directory = model_directory
        self._engine: Any = None
        self._api_version: int | None = None

    @property
    def initialized(self) -> bool:
        return self._engine is not None

    def initialize(self) -> None:
        if self._engine is not None:
            return
        if self.model_directory is not None:
            if self.language == "en" and self.model == "PP-OCRv5_mobile":
                ensure_default_ocr_models(self.model_directory)
            self.model_directory.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("PADDLE_HOME", str(self.model_directory / "paddle"))
            os.environ.setdefault(
                "PADDLE_PDX_CACHE_HOME", str(self.model_directory / "paddlex")
            )
            os.environ.setdefault(
                "HF_HOME", str(self.model_directory / "huggingface")
            )
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OCREngineError(
                "Chưa cài PaddleOCR/PaddlePaddle. Chạy scripts/setup.ps1 -Dev."
            ) from exc
        version = self.model.split("_")[0]
        device = "gpu:0" if self.use_gpu else "cpu"
        model_size = "server" if self.model.endswith("_server") else "mobile"
        recognition_name = f"{version}_{model_size}_rec"
        if model_size == "mobile" and self.language in {"en", "korean"}:
            recognition_name = f"{self.language}_{version}_mobile_rec"
        try:
            self._engine = PaddleOCR(
                text_detection_model_name=f"{version}_{model_size}_det",
                text_recognition_model_name=recognition_name,
                device=device,
                # Paddle 3.3.1 on Windows currently fails PP-OCRv5 inference
                # for some oneDNN PIR attributes. The plain CPU kernel is stable.
                enable_mkldnn=False,
                cpu_threads=self.cpu_threads,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                # PaddleX otherwise accepts desktop images up to 4000 px and
                # recognizes each text crop almost serially. A 960 px
                # detection canvas preserves ordinary UI text while making
                # full-screen OCR practical on CPU-only Windows machines.
                text_det_limit_side_len=960,
                text_det_limit_type="max",
                text_recognition_batch_size=max(1, min(8, self.cpu_threads * 2)),
                text_rec_score_thresh=self.confidence_threshold,
            )
            self._api_version = 3
        except TypeError:
            try:
                self._engine = PaddleOCR(
                    lang=self.language,
                    use_angle_cls=True,
                    use_gpu=self.use_gpu,
                    show_log=False,
                )
                self._api_version = 2
            except Exception as exc:  # Paddle raises several backend-specific errors
                raise OCREngineError(f"Không thể khởi tạo PaddleOCR: {exc}") from exc
        except Exception as exc:
            raise OCREngineError(
                "Không thể khởi tạo/tải model PaddleOCR. Kiểm tra mạng, dung lượng đĩa "
                f"và tính tương thích model '{version}' với '{self.language}': {exc}"
            ) from exc

    def extract(self, image: np.ndarray, screen_id: str) -> list[OCRBlock]:
        if image.size == 0:
            return []
        self.initialize()
        try:
            if self._api_version == 3:
                raw_results = self._engine.predict(image)
                return self._parse_v3(raw_results, screen_id)
            raw_results = self._engine.ocr(image, cls=True)
            return self._parse_v2(raw_results, screen_id)
        except OCREngineError:
            raise
        except Exception as exc:
            raise OCREngineError(f"PaddleOCR xử lý ảnh thất bại: {exc}") from exc

    def _parse_v3(self, raw_results: Iterable[Any], screen_id: str) -> list[OCRBlock]:
        blocks: list[OCRBlock] = []
        for result in raw_results:
            payload = getattr(result, "json", result)
            if callable(payload):
                payload = payload()
            if not isinstance(payload, dict):
                continue
            data = payload.get("res", payload)
            texts = list(data.get("rec_texts", []))
            scores = list(data.get("rec_scores", []))
            polygons = list(data.get("rec_polys", data.get("dt_polys", [])))
            for text, score, polygon in zip(texts, scores, polygons, strict=False):
                block = self._make_block(text, float(score), polygon, screen_id)
                if block is not None:
                    blocks.append(block)
        return self._sort_blocks(blocks)

    def _parse_v2(self, raw_results: Any, screen_id: str) -> list[OCRBlock]:
        blocks: list[OCRBlock] = []
        pages = raw_results or []
        for page in pages:
            if not page:
                continue
            for line in page:
                if not line or len(line) < 2:
                    continue
                polygon, recognition = line[0], line[1]
                text, score = recognition[0], float(recognition[1])
                block = self._make_block(text, score, polygon, screen_id)
                if block is not None:
                    blocks.append(block)
        return self._sort_blocks(blocks)

    def _make_block(
        self, text: str, confidence: float, polygon: Any, screen_id: str
    ) -> OCRBlock | None:
        cleaned = " ".join(str(text).split())
        if not cleaned or confidence < self.confidence_threshold:
            return None
        points_array = np.asarray(polygon, dtype=float).reshape(-1, 2)
        if len(points_array) < 4:
            return None
        points = tuple((round(point[0]), round(point[1])) for point in points_array)
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        box = BoundingBox(
            min(xs), min(ys), max(1, max(xs) - min(xs)), max(1, max(ys) - min(ys))
        )
        material = f"{screen_id}\x1f{cleaned}\x1f{box.x},{box.y},{box.width},{box.height}"
        block_id = hashlib.sha1(material.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
        return OCRBlock(
            id=block_id,
            text=cleaned,
            confidence=confidence,
            bounding_box=box,
            polygon=points,
            language=self.language,
            paragraph_id=block_id,
            screen_id=screen_id,
        )

    @staticmethod
    def _sort_blocks(blocks: list[OCRBlock]) -> list[OCRBlock]:
        if not blocks:
            return []
        median_height = float(np.median([block.bounding_box.height for block in blocks]))
        row_size = max(1, round(median_height * 0.7))
        return sorted(
            blocks,
            key=lambda block: (
                round(block.bounding_box.y / row_size),
                block.bounding_box.x,
            ),
        )

