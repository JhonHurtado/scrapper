# tests/test_cities.py
from backend.scraper.cities import CITIES, PRIORITY_DANE
from backend.scraper.municipalities import (all_municipalities, by_dane, find_by_name,
                                            find_mentioned, is_ambiguous_name, ordered)


def test_cities_list_has_minimum_count():
    assert len(CITIES) >= 60


def test_all_cities_have_dane_name_and_department():
    for city in CITIES:
        assert len(city["dane"]) == 5 and city["dane"].isdigit()
        assert city["name"] and city["department"]


def test_priority_cities_exist_in_divipola():
    index = by_dane()
    for city in CITIES:
        m = index[city["dane"]]
        assert m.department == city["department"], city


def test_catalog_covers_every_municipality():
    municipalities = all_municipalities()
    assert len(municipalities) >= 1100          # DIVIPOLA: 1.122
    assert sum(1 for m in municipalities if m.alcaldia_url) >= 900
    assert all(m.lat is not None and m.lng is not None for m in municipalities)
    assert all(m.alcaldia_url.split("/")[2].endswith(".gov.co")
               for m in municipalities if m.alcaldia_url)


def test_ordered_puts_priority_first_and_keeps_everyone():
    result = ordered(PRIORITY_DANE)
    assert [m.dane for m in result[:len(PRIORITY_DANE)]] == PRIORITY_DANE
    assert len({m.dane for m in result}) == len(all_municipalities())


def test_find_by_name_refuses_to_guess_homonyms():
    villanueva = [m for m in all_municipalities() if m.name == "Villanueva"]
    assert len(villanueva) > 1
    assert is_ambiguous_name(villanueva[0])
    assert find_by_name("Villanueva") is None
    assert find_by_name("Villanueva", "85").department == "Casanare"
    assert find_by_name("villa de leyva").dane == "15407"


def test_find_mentioned_prefers_first_mention_in_department():
    text = "Ubicado en Barichara, a 20 minutos de San Gil por el Camino Real"
    assert find_mentioned(text, "68").name == "Barichara"
    assert find_mentioned("Sin municipios aquí", "68") is None
