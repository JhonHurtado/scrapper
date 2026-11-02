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
    p = Place(name="Plaza de Bolívar", city="Bogotá", department="Cundinamarca",
              category="plazas", source_type="alcaldia")
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
    save_place(Place(name="Lugar A", city="Bogotá", department="Cundinamarca",
                     category="parques", source_type="alcaldia"))
    assert count_places() == 1


def test_get_places_by_city(tmp_db):
    from backend.database.models import Place, save_place, get_places_by_city
    save_place(Place(name="Lugar A", city="Bogotá", department="Cundinamarca",
                     category="parques", source_type="alcaldia"))
    save_place(Place(name="Lugar B", city="Medellín", department="Antioquia",
                     category="museos", source_type="alcaldia"))
    bogota = get_places_by_city("bogota")
    assert len(bogota) == 1
    assert bogota[0].city == "Bogotá"


def test_city_progress_flow(tmp_db):
    from backend.database.models import init_city_progress, get_pending_cities, mark_city_complete
    cities = [{"dane": "11001", "name": "Bogotá", "department": "Cundinamarca"},
              {"dane": "05001", "name": "Medellín", "department": "Antioquia"}]
    init_city_progress(cities)
    pending = get_pending_cities()
    assert len(pending) == 2
    mark_city_complete("11001", 15)
    pending_after = get_pending_cities()
    assert pending_after == [{"dane": "05001", "name": "Medellín", "department": "Antioquia"}]


def test_extract_place_coords_from_href():
    from backend.scraper.official.geocode import extract_place_coords
    href = ("https://www.google.com/maps/place/Pozo+de+Donato/data="
            "!4m7!3m6!1s0xabc!8m2!3d5.5566297!4d-73.3610534!16s")
    lat, lng = extract_place_coords(href)
    assert lat == 5.5566297
    assert lng == -73.3610534


def test_extract_place_coords_missing():
    from backend.scraper.official.geocode import extract_place_coords
    assert extract_place_coords("https://www.google.com/maps/place/x") == (None, None)


def test_extract_google_place_id():
    from backend.scraper.official.geocode import extract_google_place_id
    href = ("https://www.google.com/maps/place/Mirador/data="
            "!4m7!3m6!1s0x8e47659cd1ce58cb:0xaf820e9563eab5b2!8m2!3d5.04!4d-75.51")
    assert extract_google_place_id(href) == "0x8e47659cd1ce58cb:0xaf820e9563eab5b2"
    assert extract_google_place_id("https://www.google.com/maps/place/x") is None


def test_place_key_defaults_to_coords_then_slug():
    from backend.database.models import Place
    p = Place(name="X", city="Y", department="Z", category="nature",
              latitude=4.123456789, longitude=-74.1)
    assert p.place_key == "4.12346,-74.10000"
    q = Place(name="X", city="Y", department="Z", category="nature")
    assert q.place_key == q.slug


def test_save_place_dedupes_by_place_key(tmp_db):
    from backend.database.models import Place, save_place
    a = Place(name="Gran Malecón", city="Barranquilla", department="Atlántico",
              category="viewpoints", place_key="0xabc:0xdef")
    b = Place(name="Gran Malecón del Río", city="Bogotá", department="Cundinamarca",
              category="monuments", place_key="0xabc:0xdef")
    assert save_place(a) is True
    assert save_place(b) is False  # mismo lugar físico, otra categoría/ciudad


def test_clean_text_strips_icon_glyphs():
    from backend.scraper.official.geocode import clean_text
    assert clean_text("\ue0c8Cra. 2a #Cl. 18, Bogotá") == "Cra. 2a #Cl. 18, Bogotá"
    assert clean_text(None) == ""


def test_place_key_uses_dane_code_and_name():
    from backend.database.models import Place
    p = Place(name="Iglesia de San Francisco", city="Popayán", department="Cauca",
              category="iglesias", dane_code="19001", latitude=2.44, longitude=-76.6)
    assert p.place_key == "19001:iglesia-de-san-francisco"


def test_legacy_places_are_hidden_and_purgeable(tmp_db):
    from backend.database.models import (Place, count_legacy_places, count_places,
                                         get_all_places, purge_legacy_places, save_place)
    save_place(Place(name="Restaurante Google", city="Bogotá", department="Cundinamarca",
                     category="cultural"))  # versión anterior: sin fuente oficial
    save_place(Place(name="Museo del Oro", city="Bogotá", department="Cundinamarca",
                     category="museos", source_type="alcaldia", dane_code="11001"))
    assert [p.name for p in get_all_places()] == ["Museo del Oro"]
    assert count_places() == 1
    assert count_legacy_places() == 1
    assert len(get_all_places(include_legacy=True)) == 2
    assert purge_legacy_places() == 1
    assert count_legacy_places() == 0


def test_duplicate_fills_missing_location(tmp_db):
    from backend.database.models import Place, get_all_places, save_place
    first = Place(name="Puente de Occidente", city="Santa Fe de Antioquia",
                  department="Antioquia", category="puentes", dane_code="05042",
                  source_type="alcaldia")
    second = Place(name="Puente de Occidente", city="Santa Fe de Antioquia",
                   department="Antioquia", category="puentes", dane_code="05042",
                   source_type="datos_abiertos", latitude=6.5786, longitude=-75.8027,
                   geo_source="fuente_oficial", verified=True)
    assert save_place(first) is True
    assert save_place(second) is False
    [stored] = get_all_places()
    assert stored.latitude == 6.5786 and stored.verified is True
    assert stored.source_type == "alcaldia"  # la primera fuente se conserva


def test_init_db_migrates_previous_version(tmp_path, monkeypatch):
    """Una data.db de la versión anterior (Google Maps) se migra sin perder datos."""
    import sqlite3
    from backend.config import config
    from backend.database.db import close_db, init_db
    db_file = tmp_path / "old.db"
    old = sqlite3.connect(db_file)
    old.executescript("""
        CREATE TABLE places (id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL DEFAULT '', short_description TEXT,
            address TEXT NOT NULL DEFAULT '', city TEXT NOT NULL, city_slug TEXT,
            department TEXT NOT NULL, country TEXT NOT NULL DEFAULT 'Colombia',
            latitude REAL, longitude REAL, main_image TEXT, phone TEXT, email TEXT,
            website TEXT, category TEXT NOT NULL, scraped_at TEXT NOT NULL, source_url TEXT);
        CREATE TABLE city_progress (city_slug TEXT PRIMARY KEY, city_name TEXT NOT NULL,
            department TEXT NOT NULL, status TEXT DEFAULT 'pending',
            places_found INTEGER DEFAULT 0, completed_at TEXT);
        INSERT INTO places (id, name, slug, city, department, category, scraped_at)
            VALUES ('1', 'Mirador X', 'mirador-x-bogota', 'Bogotá', 'Cundinamarca',
                    'viewpoints', '2026-01-01');
        INSERT INTO city_progress (city_slug, city_name, department) VALUES ('bogota', 'Bogotá', 'Cundinamarca');
    """)
    old.commit()
    old.close()

    monkeypatch.setattr(config, "db_path", db_file)
    close_db()
    init_db()
    from backend.database.models import count_legacy_places, count_places, get_pending_cities
    assert count_legacy_places() == 1 and count_places() == 0
    assert get_pending_cities() == []
    close_db()
