# backend/database/db.py
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS places (
                id               TEXT PRIMARY KEY,
                name             TEXT NOT NULL,
                slug             TEXT UNIQUE NOT NULL,
                description      TEXT NOT NULL DEFAULT '',
                short_description TEXT,
                address          TEXT NOT NULL DEFAULT '',
                city             TEXT NOT NULL,
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
                source_url       TEXT
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
        """)
