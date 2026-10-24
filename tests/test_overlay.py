from app.core.config import AppSettings
from app.core.models import BoundingBox, OverlayBlock
from app.overlay.overlay_window import TranslationOverlay


def test_overlay_assigns_blocks_to_screen(qtbot, tmp_path):
    overlay = TranslationOverlay(AppSettings(data_dir=tmp_path))
    block = OverlayBlock(
        "1", "Hello", "Xin chào", BoundingBox(10, 10, 180, 40), "monitor-1"
    )
    overlay.set_blocks([block])
    window = overlay._windows["monitor-1"]
    qtbot.addWidget(window)
    assert window.blocks == [block]
    assert window.isVisible()
    overlay.clear()
    assert not window.isVisible()

