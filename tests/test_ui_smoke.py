from app.core.config import AppSettings
from app.core.events import ApplicationEvents
from app.database.db import Database
from app.ui.main_window import MainWindow


def test_main_window_constructs_all_pages(qtbot, tmp_path):
    settings = AppSettings(data_dir=tmp_path)
    window = MainWindow(
        settings,
        ApplicationEvents(engine_available=False),
        Database(settings.database_path),
    )
    qtbot.addWidget(window)

    assert window.stack.count() == 5
    assert len(window.navigation) == 5
    assert window.windowTitle() == "LiveScreen Translator Pro"

