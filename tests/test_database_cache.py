from app.core.models import TranslationResult
from app.database.db import Database
from app.translation.cache import TranslationCache


def test_translation_cache_round_trip(tmp_path):
    database = Database(tmp_path / "test.db")
    cache = TranslationCache(database)
    result = TranslationResult("Hello", "Xin chào", "EN", "deepl", 5)
    cache.put(result, "EN", "VI")

    cached = cache.get("Hello", "deepl", "EN", "VI")

    assert cached is not None
    assert cached.translated_text == "Xin chào"
    assert cached.from_cache
    assert cached.billed_characters == 0


def test_history_can_be_searched_and_cleared(tmp_path):
    database = Database(tmp_path / "test.db")
    database.add_history(None, "Book", "Sách", "EN", "VI", "google")
    assert database.history("Sách")[0].source_text == "Book"
    database.clear_history()
    assert database.history() == []

