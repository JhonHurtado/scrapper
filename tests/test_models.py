# tests/test_models.py
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    from backend.config import config
    from backend.database.db import close_db, init_db
    monkeypatch.setattr(config, "db_path", db_file)
    close_db()
    init_db()
    yield db_file
    close_db()


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


def test_extract_coords_from_url():
    from backend.scraper.playwright_scraper import _extract_coords
    url = "https://www.google.com/maps/place/Plaza/@4.5981,-74.0759,17z/data=..."
    lat, lng = _extract_coords(url)
    assert lat == 4.5981
    assert lng == -74.0759


def test_extract_coords_missing():
    from backend.scraper.playwright_scraper import _extract_coords
    lat, lng = _extract_coords("https://www.google.com/maps/search/bogota")
    assert lat is None
    assert lng is None


def test_extract_place_coords_from_href():
    from backend.scraper.playwright_scraper import _extract_place_coords
    href = ("https://www.google.com/maps/place/Pozo+de+Donato/data="
            "!4m7!3m6!1s0xabc!8m2!3d5.5566297!4d-73.3610534!16s")
    lat, lng = _extract_place_coords(href)
    assert lat == 5.5566297
    assert lng == -73.3610534


def test_extract_place_coords_missing():
    from backend.scraper.playwright_scraper import _extract_place_coords
    assert _extract_place_coords("https://www.google.com/maps/place/x") == (None, None)


def test_clean_text_strips_icon_glyphs():
    from backend.scraper.playwright_scraper import _clean_text
    assert _clean_text("Cra. 2a #Cl. 18, Bogotá") == "Cra. 2a #Cl. 18, Bogotá"
    assert _clean_text(None) == ""
