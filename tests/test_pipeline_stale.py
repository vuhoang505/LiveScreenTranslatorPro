import numpy as np

from app.controllers.auto_translation import _PipelineWorker
from app.core.models import BoundingBox, ScreenFrame


def test_changed_page_is_detected_before_overlay_update():
    original = ScreenFrame(
        "monitor-1",
        1,
        np.zeros((100, 200, 3), dtype=np.uint8),
        BoundingBox(0, 0, 200, 100),
    )
    changed = ScreenFrame(
        "monitor-1",
        1,
        np.full((100, 200, 3), 255, dtype=np.uint8),
        BoundingBox(0, 0, 200, 100),
    )

    hashes = {original.screen_id: _PipelineWorker._frame_hash(original)}

    assert _PipelineWorker._frames_changed(hashes, [changed])


def test_tiny_clock_or_caret_change_does_not_discard_ocr_result():
    first_hash = np.zeros(64, dtype=bool)
    second_hash = first_hash.copy()
    second_hash[:20] = True
    first_thumbnail = np.zeros((36, 64), dtype=np.uint8)
    second_thumbnail = first_thumbnail.copy()
    second_thumbnail[0, 0] = 255

    distance = _PipelineWorker._hash_distance(
        (first_hash, first_thumbnail), (second_hash, second_thumbnail)
    )

    assert distance == 0


def test_small_changed_area_uses_expanded_incremental_ocr_region():
    frame = ScreenFrame(
        "monitor-1",
        1,
        np.zeros((500, 1000, 3), dtype=np.uint8),
        BoundingBox(0, 0, 1000, 500),
    )

    regions = _PipelineWorker._regions_for_ocr(
        frame, (BoundingBox(100, 120, 30, 20),)
    )

    assert regions == (BoundingBox(52, 72, 126, 116),)


def test_broad_change_falls_back_to_full_screen_ocr():
    frame = ScreenFrame(
        "monitor-1",
        1,
        np.zeros((500, 1000, 3), dtype=np.uint8),
        BoundingBox(0, 0, 1000, 500),
    )

    regions = _PipelineWorker._regions_for_ocr(
        frame, (BoundingBox(0, 0, 900, 400),)
    )

    assert regions == (BoundingBox(0, 0, 1000, 500),)


def test_many_changed_areas_use_one_full_screen_inference():
    frame = ScreenFrame(
        "monitor-1",
        1,
        np.zeros((600, 1200, 3), dtype=np.uint8),
        BoundingBox(0, 0, 1200, 600),
    )

    regions = _PipelineWorker._regions_for_ocr(
        frame,
        (
            BoundingBox(20, 20, 20, 20),
            BoundingBox(350, 20, 20, 20),
            BoundingBox(700, 20, 20, 20),
            BoundingBox(1050, 500, 20, 20),
        ),
    )

    assert regions == (BoundingBox(0, 0, 1200, 600),)
