import pytest

from app.core.hotkeys import MOD_ALT, MOD_CONTROL, GlobalHotkeyManager


def test_hotkey_parser_supports_requested_shortcuts():
    modifiers, key = GlobalHotkeyManager._parse("Ctrl+Alt+T")
    assert modifiers == MOD_CONTROL | MOD_ALT
    assert key == ord("T")


def test_hotkey_parser_rejects_unknown_keys():
    with pytest.raises(ValueError):
        GlobalHotkeyManager._parse("Ctrl+Alt+LaunchTranslator")

