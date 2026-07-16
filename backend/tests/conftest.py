# backend/tests/conftest.py
import os
import pytest
import sqlite3

TEST_DB_CONN = None


@pytest.fixture(autouse=True)
def fresh_db():
    global TEST_DB_CONN

    from backend.database import db as db_module
    if db_module._connection:
        try:
            db_module._connection.close()
        except Exception:
            pass
    db_module._connection = None

    TEST_DB_CONN = sqlite3.connect(":memory:", check_same_thread=False)
    TEST_DB_CONN.row_factory = sqlite3.Row

    db_module._connection = TEST_DB_CONN

    conn = db_module.get_connection()
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

        CREATE UNIQUE INDEX IF NOT EXISTS idx_places_place_key ON places(place_key);

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

    yield

    if TEST_DB_CONN:
        TEST_DB_CONN.close()
    TEST_DB_CONN = None
    db_module._connection = None


@pytest.fixture
def temp_db():
    pass


@pytest.fixture
def sample_place_data():
    return {
        "name": "Parque Principal",
        "city": "Bogotá",
        "department": "Cundinamarca",
        "category": "nature",
        "description": "Un parque hermoso en el centro de la ciudad",
        "address": "Calle 1 # 1-1",
        "latitude": 4.6097,
        "longitude": -74.0817,
        "main_image": "https://example.com/image.jpg",
        "phone": "+57 1 123 4567",
        "website": "https://example.com",
        "source_url": "https://www.google.com/maps/place/test",
    }