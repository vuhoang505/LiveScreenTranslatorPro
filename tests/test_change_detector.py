import numpy as np

from app.capture.change_detector import ScreenChangeDetector


def test_static_screen_does_not_repeat_ocr():
    detector = ScreenChangeDetector(threshold=0.02, debounce_seconds=0.5)
    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    assert detector.analyze("one", frame, now=0).should_process
    result = detector.analyze("one", frame.copy(), now=1)
    assert not result.should_process
    assert not result.changed


def test_scroll_change_waits_until_stable():
    detector = ScreenChangeDetector(threshold=0.02, debounce_seconds=0.5)
    first = np.zeros((200, 300, 3), dtype=np.uint8)
    second = first.copy()
    second[40:170, 30:270] = 255
    detector.analyze("one", first, now=0)
    moving = detector.analyze("one", second, now=0.1)
    waiting = detector.analyze("one", second, now=0.4)
    stable = detector.analyze("one", second, now=0.7)
    assert moving.changed and not moving.stable
    assert not waiting.should_process
    assert stable.should_process and stable.stable


def test_cursor_sized_change_is_ignored():
    detector = ScreenChangeDetector(threshold=0.02, debounce_seconds=0.2)
    first = np.zeros((300, 400, 3), dtype=np.uint8)
    cursor = first.copy()
    cursor[10:15, 10:15] = 255
    detector.analyze("one", first, now=0)
    result = detector.analyze("one", cursor, now=1)
    assert not result.should_process

