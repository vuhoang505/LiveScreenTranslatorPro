import numpy as np

from app.capture.screen_capture import ScreenCaptureService
from app.core.models import BoundingBox


class FakeMSS:
    monitors = [
        {"left": 0, "top": 0, "width": 300, "height": 100},
        {"left": -100, "top": 0, "width": 100, "height": 100},
        {"left": 0, "top": 0, "width": 200, "height": 100},
    ]

    def grab(self, monitor):
        return np.zeros((monitor["height"], monitor["width"], 4), dtype=np.uint8)

    def close(self):
        return None


def test_capture_all_monitors_stays_in_memory():
    service = ScreenCaptureService()
    service._local.backend = FakeMSS()
    frames = service.capture(0)
    assert len(frames) == 2
    assert frames[0].physical_bounds == BoundingBox(-100, 0, 100, 100)
    assert frames[1].image.shape == (100, 200, 3)


def test_capture_single_monitor():
    service = ScreenCaptureService()
    service._local.backend = FakeMSS()
    frames = service.capture(2)
    assert [frame.screen_id for frame in frames] == ["monitor-2"]

