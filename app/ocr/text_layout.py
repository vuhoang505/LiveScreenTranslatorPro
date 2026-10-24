from __future__ import annotations

import hashlib
from statistics import median

from app.core.models import OCRBlock, TextParagraph


def _horizontal_overlap(first: OCRBlock, second: OCRBlock) -> float:
    left = max(first.bounding_box.x, second.bounding_box.x)
    right = min(first.bounding_box.right, second.bounding_box.right)
    overlap = max(0, right - left)
    return overlap / max(1, min(first.bounding_box.width, second.bounding_box.width))


def group_into_paragraphs(blocks: list[OCRBlock]) -> list[TextParagraph]:
    """Group adjacent OCR lines without merging neighboring document columns."""
    if not blocks:
        return []
    typical_height = median(block.bounding_box.height for block in blocks)
    ordered = sorted(blocks, key=lambda block: (block.bounding_box.y, block.bounding_box.x))
    groups: list[list[OCRBlock]] = []
    for block in ordered:
        best_group: list[OCRBlock] | None = None
        best_distance = float("inf")
        for group in groups:
            previous = group[-1]
            vertical_gap = block.bounding_box.y - previous.bounding_box.bottom
            aligned = (
                _horizontal_overlap(previous, block) >= 0.18
                or abs(previous.bounding_box.x - block.bounding_box.x)
                <= typical_height * 1.5
            )
            if -typical_height * 0.3 <= vertical_gap <= typical_height * 1.25 and aligned:
                distance = abs(vertical_gap)
                if distance < best_distance:
                    best_group = group
                    best_distance = distance
        if best_group is None:
            groups.append([block])
        else:
            best_group.append(block)

    paragraphs: list[TextParagraph] = []
    for group in groups:
        group.sort(key=lambda block: (block.bounding_box.y, block.bounding_box.x))
        box = group[0].bounding_box
        for block in group[1:]:
            box = box.union(block.bounding_box)
        text = "\n".join(block.text for block in group)
        material = "\x1f".join(block.id for block in group)
        paragraph_id = hashlib.sha1(
            material.encode("utf-8"), usedforsecurity=False
        ).hexdigest()[:16]
        paragraphs.append(
            TextParagraph(
                id=paragraph_id,
                text=text,
                confidence=sum(block.confidence for block in group) / len(group),
                bounding_box=box,
                block_ids=tuple(block.id for block in group),
                screen_id=group[0].screen_id,
            )
        )
    return sorted(paragraphs, key=lambda item: (item.bounding_box.y, item.bounding_box.x))

