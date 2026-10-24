from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from app.database.models import ApiUsageRecord, HistoryRecord

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS translation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    source_language TEXT,
    target_language TEXT NOT NULL,
    provider TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES translation_sessions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS translation_cache (
    cache_key TEXT PRIMARY KEY,
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    detected_language TEXT,
    provider TEXT NOT NULL,
    source_language TEXT,
    target_language TEXT NOT NULL,
    character_count INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    hit_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS application_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS translation_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    translated_segments INTEGER NOT NULL DEFAULT 0,
    character_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    character_count INTEGER NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_history_created ON translation_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_source ON translation_history(source_text);
CREATE INDEX IF NOT EXISTS idx_usage_provider ON api_usage(provider, created_at);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def start_session(self) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("INSERT INTO translation_sessions DEFAULT VALUES")
            return int(cursor.lastrowid)

    def end_session(self, session_id: int, segments: int, characters: int) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE translation_sessions
                SET ended_at=CURRENT_TIMESTAMP, translated_segments=?, character_count=?
                WHERE id=?
                """,
                (segments, characters, session_id),
            )

    def get_cache(self, cache_key: str) -> sqlite3.Row | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM translation_cache WHERE cache_key=?", (cache_key,)
            ).fetchone()
            if row is not None:
                connection.execute(
                    """
                    UPDATE translation_cache
                    SET last_used_at=CURRENT_TIMESTAMP, hit_count=hit_count+1
                    WHERE cache_key=?
                    """,
                    (cache_key,),
                )
            return row

    def put_cache(
        self,
        cache_key: str,
        source_text: str,
        translated_text: str,
        detected_language: str | None,
        provider: str,
        source_language: str | None,
        target_language: str,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO translation_cache(
                    cache_key, source_text, translated_text, detected_language, provider,
                    source_language, target_language, character_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    translated_text=excluded.translated_text,
                    detected_language=excluded.detected_language,
                    last_used_at=CURRENT_TIMESTAMP
                """,
                (
                    cache_key,
                    source_text,
                    translated_text,
                    detected_language,
                    provider,
                    source_language,
                    target_language,
                    len(source_text),
                ),
            )

    def add_history(
        self,
        session_id: int | None,
        source_text: str,
        translated_text: str,
        source_language: str | None,
        target_language: str,
        provider: str,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO translation_history(
                    session_id, source_text, translated_text, source_language,
                    target_language, provider
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    source_text,
                    translated_text,
                    source_language,
                    target_language,
                    provider,
                ),
            )

    def add_usage(self, provider: str, characters: int) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO api_usage(provider, character_count) VALUES (?, ?)",
                (provider, characters),
            )

    def usage_totals(self) -> list[ApiUsageRecord]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT provider, COALESCE(SUM(character_count), 0) AS character_count,
                       COALESCE(SUM(request_count), 0) AS request_count
                FROM api_usage GROUP BY provider ORDER BY provider
                """
            ).fetchall()
        return [
            ApiUsageRecord(row["provider"], row["character_count"], row["request_count"])
            for row in rows
        ]

    def history(self, search: str = "", limit: int = 500) -> list[HistoryRecord]:
        query = """
            SELECT id, source_text, translated_text, source_language,
                   target_language, provider, created_at
            FROM translation_history
        """
        parameters: tuple[object, ...]
        if search.strip():
            query += " WHERE source_text LIKE ? OR translated_text LIKE ?"
            pattern = f"%{search.strip()}%"
            parameters = (pattern, pattern, limit)
        else:
            parameters = (limit,)
        query += " ORDER BY id DESC LIMIT ?"
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [HistoryRecord(**dict(row)) for row in rows]

    def clear_history(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM translation_history")

    def clear_cache(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM translation_cache")

    def close(self) -> None:
        """Connections are short-lived; retained for a uniform shutdown interface."""

