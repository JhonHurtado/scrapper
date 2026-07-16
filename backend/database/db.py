# backend/database/db.py
import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path

from ..config import config

logger = logging.getLogger(__name__)

_connection = None


def get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        config.db_path.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(str(config.db_path), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
    return _connection


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pass


def close_db():
    global _connection
    if _connection:
        _connection.close()
        _connection = None


def reset_db():
    global _connection
    if _connection:
        _connection.close()
        _connection = None
    config.db_path.unlink(missing_ok=True)


def init_db():
    logger.info(f"Initializing database at {config.db_path}")
    config.db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS places (
            id               TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            slug             TEXT UNIQUE NOT NULL,
            description      TEXT NOT NULL DEFAULT '',
            short_description TEXT,
            address          TEXT NOT NULL DEFAULT '',
            city             TEXT NOT NULL,
            city_slug        TEXT,
            department       TEXT NOT NULL,
            country          TEXT NOT NULL DEFAULT 'Colombia',
            latitude         REAL,
            longitude        REAL,
            main_image       TEXT,
            phone            TEXT,
            email            TEXT,
            website          TEXT,
            category         TEXT NOT NULL,
            scraped_at       TEXT NOT NULL,
            source_url       TEXT,
            place_key        TEXT
        );

        CREATE TABLE IF NOT EXISTS scrape_sessions (
            id               TEXT PRIMARY KEY,
            started_at       TEXT NOT NULL,
            completed_at     TEXT,
            cities_processed INTEGER DEFAULT 0,
            total_places     INTEGER DEFAULT 0,
            status           TEXT DEFAULT 'running'
        );

        CREATE TABLE IF NOT EXISTS city_progress (
            city_slug    TEXT PRIMARY KEY,
            city_name    TEXT NOT NULL,
            department   TEXT NOT NULL,
            status       TEXT DEFAULT 'pending',
            places_found INTEGER DEFAULT 0,
            completed_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_places_city_slug ON places(city_slug);
        CREATE INDEX IF NOT EXISTS idx_places_department ON places(department);
        CREATE INDEX IF NOT EXISTS idx_places_category ON places(category);
        CREATE INDEX IF NOT EXISTS idx_places_name ON places(name);
        CREATE INDEX IF NOT EXISTS idx_city_progress_status ON city_progress(status);
    """)

    # Migración: bases creadas antes de place_key
    cols = [r[1] for r in conn.execute("PRAGMA table_info(places)")]
    if "place_key" not in cols:
        conn.execute("ALTER TABLE places ADD COLUMN place_key TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_places_place_key ON places(place_key)"
    )
    conn.commit()
    logger.info("Database initialized successfully")