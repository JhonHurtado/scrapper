# backend/tests/test_models.py
import pytest
from backend.database.models import Place, save_place, count_places, get_all_places, get_places_by_city


def test_place_creation():
    place = Place(
        name="Test Place",
        city="Bogotá",
        department="Cundinamarca",
        category="monuments",
    )
    assert place.name == "Test Place"
    assert place.city == "Bogotá"
    assert place.id is not None
    assert place.slug is not None
    assert place.scraped_at is not None


def test_place_to_dict():
    place = Place(
        name="Test Place",
        city="Bogotá",
        department="Cundinamarca",
        category="monuments",
        description="A test description",
        address="Test Address",
    )
    d = place.to_dict()
    assert d["name"] == "Test Place"
    assert d["city"] == "Bogotá"
    assert d["department"] == "Cundinamarca"
    assert d["category"] == "monuments"
    assert d["description"] == "A test description"
    assert d["shortDescription"] == "A test description"[:160]


def test_save_place(sample_place_data):
    place = Place(**sample_place_data)
    result = save_place(place)
    assert result is True
    assert count_places() == 1


def test_save_duplicate_place(sample_place_data):
    place1 = Place(**sample_place_data)
    place2 = Place(**sample_place_data)
    assert save_place(place1) is True
    assert save_place(place2) is False
    assert count_places() == 1


def test_get_all_places(sample_place_data):
    place1 = Place(**sample_place_data)
    place2 = Place(**{**sample_place_data, "name": "Another Place", "city": "Medellín"})
    save_place(place1)
    save_place(place2)
    places = get_all_places()
    assert len(places) == 2


def test_get_places_by_city(sample_place_data):
    place1 = Place(**sample_place_data)
    place2 = Place(**{**sample_place_data, "name": "Medellín Place", "city": "Medellín"})
    save_place(place1)
    save_place(place2)
    bogota_places = get_places_by_city("bogota")
    assert len(bogota_places) == 1
    assert bogota_places[0].name == "Parque Principal"