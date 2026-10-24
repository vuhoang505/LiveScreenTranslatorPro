from app.core.models import BoundingBox, OCRBlock
from app.ocr.ocr_engine import OCREngine
from app.ocr.text_layout import group_into_paragraphs


def test_paddle_v3_result_extraction_filters_low_confidence():
    engine = OCREngine(confidence_threshold=0.7)
    raw = [
        {
            "res": {
                "rec_texts": ["First line", "noise"],
                "rec_scores": [0.98, 0.2],
                "rec_polys": [
                    [[10, 10], [110, 10], [110, 30], [10, 30]],
                    [[0, 0], [4, 0], [4, 4], [0, 4]],
                ],
            }
        }
    ]
    blocks = engine._parse_v3(raw, "monitor-1")
    assert len(blocks) == 1
    assert blocks[0].text == "First line"
    assert blocks[0].bounding_box == BoundingBox(10, 10, 100, 20)


def test_adjacent_lines_are_grouped_into_paragraph():
    blocks = [
        OCRBlock("1", "Hello", 0.9, BoundingBox(10, 10, 100, 20), (), "en", "1", "s"),
        OCRBlock("2", "world", 0.9, BoundingBox(10, 35, 100, 20), (), "en", "2", "s"),
        OCRBlock("3", "Other", 0.9, BoundingBox(400, 10, 100, 20), (), "en", "3", "s"),
    ]
    paragraphs = group_into_paragraphs(blocks)
    assert len(paragraphs) == 2
    assert any(paragraph.text == "Hello\nworld" for paragraph in paragraphs)

