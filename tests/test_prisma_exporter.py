# tests/test_prisma_exporter.py
from backend.database.models import Place
from backend.exporters.prisma_exporter import build_seed_data


def _place(name, city="Bogotá", lat=4.60, lng=-74.08, **kw):
    return Place(name=name, city=city, department="Cundinamarca",
                 category="monuments", latitude=lat, longitude=lng, **kw)


def test_drops_places_without_coords():
    data = build_seed_data([_place("A"), _place("B", lat=None, lng=None)])
    assert data["metadata"]["dropped_no_coords"] == 1
    assert [p["name"] for p in data["places"]] == ["A"]


def test_drops_outliers_far_from_city_median():
    places = [
        _place("A", lat=4.60, lng=-74.08),
        _place("B", lat=4.61, lng=-74.07),
        _place("C", lat=4.59, lng=-74.09),
        _place("Lejano", lat=11.0, lng=-74.8),  # Barranquilla, etiquetado Bogotá
    ]
    data = build_seed_data(places)
    names = [p["name"] for p in data["places"]]
    assert "Lejano" not in names
    assert data["metadata"]["dropped_outliers"] == 1


def test_drops_coords_outside_colombia():
    data = build_seed_data([_place("CostaRica", lat=10.9, lng=-84.75)])
    assert data["places"] == []


def test_description_and_address_never_empty():
    data = build_seed_data([_place("Plaza Mayor")])
    p = data["places"][0]
    assert p["description"]
    assert "Plaza Mayor" in p["description"]
    assert p["address"] == "Bogotá, Cundinamarca, Colombia"
    assert p["shortDescription"]


def test_categories_included():
    data = build_seed_data([])
    slugs = {c["slug"] for c in data["categories"]}
    assert slugs == {"monumentos", "naturaleza", "miradores", "cultura"}
