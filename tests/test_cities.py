# tests/test_cities.py
from backend.scraper.cities import CITIES
from backend.scraper.queries import CATEGORY_QUERIES, build_queries_for_city


def test_cities_list_has_minimum_count():
    assert len(CITIES) >= 60


def test_all_cities_have_name_and_department():
    for city in CITIES:
        assert "name" in city and city["name"]
        assert "department" in city and city["department"]


def test_category_queries_has_four_categories():
    assert set(CATEGORY_QUERIES.keys()) == {"monuments", "nature", "viewpoints", "cultural"}


def test_build_queries_for_city_substitutes_city_name():
    queries = build_queries_for_city("Bogotá")
    assert any("Bogotá" in q["query"] for q in queries)
    assert all("category" in q for q in queries)


def test_build_queries_returns_all_categories():
    queries = build_queries_for_city("Cali")
    categories = {q["category"] for q in queries}
    assert categories == {"monuments", "nature", "viewpoints", "cultural"}
