from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

import ctranslate2
import sentencepiece as spm

from app.core.models import TranslationResult
from app.core.resources import bundled_translation_model_directory
from app.translation.base_provider import ProviderConfig, TranslationError, TranslationProvider


class OfflineProvider(TranslationProvider):
    """Bundled English-to-Vietnamese neural translation via CTranslate2."""

    name = "offline"

    def __init__(
        self,
        config: ProviderConfig,
        model_directory: Path | None = None,
    ) -> None:
        super().__init__(config)
        self.model_directory = model_directory or bundled_translation_model_directory()
        self._translator: Any = None
        self._tokenizer: Any = None
        self._lock = threading.RLock()

    def _initialize(self) -> None:
        if self._translator is not None:
            return
        model_path = self.model_directory / "model"
        tokenizer_path = self.model_directory / "sentencepiece.model"
        if not (model_path / "model.bin").is_file() or not tokenizer_path.is_file():
            raise TranslationError(
                "Bản phát hành thiếu model dịch offline Anh → Việt. "
                "Hãy cài lại bản đầy đủ của chương trình."
            )
        try:
            # SentencePiece's Windows file loader cannot open every Unicode
            # path. Loading the bytes in Python keeps installs under Vietnamese
            # user/folder names working.
            self._tokenizer = spm.SentencePieceProcessor(
                model_proto=tokenizer_path.read_bytes()
            )
            self._translator = ctranslate2.Translator(
                str(model_path),
                device="cpu",
                inter_threads=1,
                intra_threads=4,
                compute_type="auto",
            )
        except Exception as exc:
            raise TranslationError(f"Không thể nạp bộ dịch offline: {exc}") from exc

    def initialize(self) -> None:
        """Load the bundled model without running an unnecessary translation."""
        with self._lock:
            self._initialize()

    @staticmethod
    def _split_text(text: str, max_characters: int = 420) -> list[str]:
        text = " ".join(text.split())
        if not text:
            return [""]
        sentences = re.split(r"(?<=[.!?。！？])\s+", text)
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            words = sentence.split()
            while words:
                word = words[0]
                candidate = f"{current} {word}".strip()
                if len(candidate) <= max_characters:
                    current = candidate
                    words.pop(0)
                    continue
                if current:
                    chunks.append(current)
                    current = ""
                    continue
                words.pop(0)
                chunks.extend(
                    word[index : index + max_characters]
                    for index in range(0, len(word), max_characters)
                )
        if current:
            chunks.append(current)
        return chunks or [""]

    def translate_many(
        self,
        texts: list[str],
        source_language: str | None,
        target_language: str,
    ) -> list[TranslationResult]:
        source = (source_language or "EN").upper()
        target = target_language.upper()
        if source not in {"AUTO", "EN"} or target != "VI":
            raise TranslationError(
                "Chế độ offline tích hợp hiện hỗ trợ Anh → Việt. "
                "Hãy chọn nguồn English/Tự động và đích Tiếng Việt."
            )
        if not texts:
            return []

        with self._lock:
            self._initialize()
            groups = [self._split_text(text) for text in texts]
            pieces = [chunk for group in groups for chunk in group]
            try:
                tokenized = [
                    self._tokenizer.encode(piece, out_type=str) for piece in pieces
                ]
                translated = self._translator.translate_batch(
                    tokenized,
                    # Greedy decoding is materially faster and better suited to
                    # rapidly changing on-screen text than multi-beam search.
                    beam_size=1,
                    num_hypotheses=1,
                    max_batch_size=48,
                    batch_type="tokens",
                    replace_unknowns=True,
                )
                decoded = [
                    self._tokenizer.decode_pieces(item.hypotheses[0])
                    .replace("▁", " ")
                    .replace("_", " ")
                    .strip()
                    for item in translated
                ]
            except Exception as exc:
                raise TranslationError(f"Bộ dịch offline xử lý thất bại: {exc}") from exc

        results: list[TranslationResult] = []
        offset = 0
        for text, group in zip(texts, groups, strict=True):
            count = len(group)
            output = " ".join(decoded[offset : offset + count]).strip()
            offset += count
            results.append(
                TranslationResult(
                    source_text=text,
                    translated_text=output,
                    detected_language="EN",
                    provider=self.name,
                    billed_characters=0,
                )
            )
        return results

    def test_connection(self) -> None:
        result = self.translate_many(["Hello."], "EN", "VI")
        if not result or not result[0].translated_text:
            raise TranslationError("Model dịch offline không trả về kết quả.")
