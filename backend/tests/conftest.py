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

    # Mismo esquema (y migraciones) que la app real.
    db_module.init_db()

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
        "category": "parques",
        "description": "Un parque hermoso en el centro de la ciudad",
        "address": "Calle 1 # 1-1",
        "latitude": 4.6097,
        "longitude": -74.0817,
        "main_image": "https://example.com/image.jpg",
        "phone": "+57 1 123 4567",
        "website": "https://example.com",
        "source_url": "https://bogota.gov.co/mi-ciudad/turismo/parque-principal",
        "source_type": "alcaldia",
        "source_entity": "Alcaldía de Bogotá (Cundinamarca)",
        "dane_code": "11001",
        "verified": True,
    }