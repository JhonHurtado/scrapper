# tests/test_models.py
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("backend.database.db.DB_PATH", db_file)
    from backend.database.db import init_db
    init_db()
    return db_file


def test_save_and_retrieve_place(tmp_db):
    from backend.database.models import Place, save_place, get_all_places
    p = Place(name="Plaza de Bolívar", city="Bogotá", department="Cundinamarca", category="monuments")
    assert save_place(p) is True
    places = get_all_places()
    assert len(places) == 1
    assert places[0].name == "Plaza de Bolívar"
    assert places[0].slug == "plaza-de-bolivar-bogota"


def test_duplicate_slug_returns_false(tmp_db):
    from backend.database.models import Place, save_place
    p1 = Place(name="Plaza de Bolívar", city="Bogotá", department="Cundinamarca", category="monuments")
    p2 = Place(name="Plaza de Bolívar", city="Bogotá", department="Cundinamarca", category="cultural")
    assert save_place(p1) is True
    assert save_place(p2) is False  # mismo slug


def test_place_to_dict_uses_camel_case(tmp_db):
    from backend.database.models import Place
    p = Place(name="Cerro", city="Cali", department="Valle del Cauca", category="viewpoints",
              main_image="https://img.example.com/cerro.jpg")
    d = p.to_dict()
    assert "mainImage" in d
    assert "shortDescription" in d
    assert "main_image" not in d


def test_short_description_auto_generated(tmp_db):
    from backend.database.models import Place
    long_desc = "A" * 200
    p = Place(name="X", city="Y", department="Z", category="nature", description=long_desc)
    assert len(p.short_description) == 160


def test_count_places(tmp_db):
    from backend.database.models import Place, save_place, count_places
    assert count_places() == 0
    save_place(Place(name="Lugar A", city="Bogotá", department="Cundinamarca", category="nature"))
    assert count_places() == 1


def test_get_places_by_city(tmp_db):
    from backend.database.models import Place, save_place, get_places_by_city
    save_place(Place(name="Lugar A", city="Bogotá", department="Cundinamarca", category="nature"))
    save_place(Place(name="Lugar B", city="Medellín", department="Antioquia", category="cultural"))
    bogota = get_places_by_city("bogota")
    assert len(bogota) == 1
    assert bogota[0].city == "Bogotá"


def test_city_progress_flow(tmp_db):
    from backend.database.models import init_city_progress, get_pending_cities, mark_city_complete
    cities = [{"name": "Bogotá", "department": "Cundinamarca"},
              {"name": "Medellín", "department": "Antioquia"}]
    init_city_progress(cities)
    pending = get_pending_cities()
    assert len(pending) == 2
    mark_city_complete("Bogotá", "Cundinamarca", 15)
    pending_after = get_pending_cities()
    assert len(pending_after) == 1
    assert pending_after[0]["name"] == "Medellín"
