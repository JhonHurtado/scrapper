# tests/test_prisma_exporter.py
from backend.database.models import Place
from backend.exporters.prisma_exporter import build_seed_data


def _place(name, category="iglesias", lat=5.6325, lng=-73.5249, **kw):
    defaults = dict(city="Villa de Leyva", department="Boyacá", dane_code="15407",
                    source_type="alcaldia", source_entity="Alcaldía de Villa de Leyva (Boyacá)",
                    source_url="https://www.villadeleyva-boyaca.gov.co/MiMunicipio/Paginas/Sitios-de-Interes.aspx",
                    verified=lat is not None, geo_source="openstreetmap", geo_distance_km=0.1)
    defaults.update(kw)
    return Place(name=name, category=category, latitude=lat, longitude=lng, **defaults)


def test_output_matches_backend_seed_format():
    data = build_seed_data([_place("Iglesia Nuestra Señora del Rosario"),
                            _place("Casa Museo Antonio Nariño", category="museos")])
    assert set(data) == {"metadata", "categories"}
    assert data["metadata"]["total_kept"] == 2
    assert set(data["categories"]) == {"iglesias", "museos"}
    lugar = data["categories"]["museos"][0]
    # Campos que lee backend-cityscout-2.0/prisma/seed-places.ts (LugarOrigen)
    for key in ("name", "slug", "description", "shortDescription", "address", "city",
                "department", "country", "latitude", "longitude", "mainImage",
                "phone", "email", "website"):
        assert key in lugar
    assert lugar["sourceUrl"].startswith("https://www.villadeleyva-boyaca.gov.co")
    assert lugar["sourceEntity"] == "Alcaldía de Villa de Leyva (Boyacá)"


def test_only_official_and_verified_places_are_exported():
    places = [
        _place("Plaza Mayor", category="plazas"),
        _place("Molino de la Primavera", category="sitios_culturales", lat=None, lng=None),
        _place("Restaurante X", category="cultural", source_type=""),
    ]
    data = build_seed_data(places)
    assert data["metadata"]["total_kept"] == 1
    assert data["metadata"]["excluded_reasons"] == {
        "sin_ubicacion_verificada": 1, "sin_fuente_oficial": 1,
    }


def test_drops_coords_outside_colombia():
    data = build_seed_data([_place("Iglesia Lejana", lat=10.9, lng=-84.75)])
    assert data["categories"] == {}
    assert data["metadata"]["excluded_reasons"] == {"fuera_de_colombia": 1}


def test_excluded_categories_never_exported():
    data = build_seed_data([_place("Termales del Ruiz", category="termales")])
    assert data["metadata"]["total_kept"] == 0


def test_empty_description_is_left_for_backend_fallback():
    lugar = build_seed_data([_place("Plaza Mayor", category="plazas")])["categories"]["plazas"][0]
    assert lugar["description"] is None
    assert lugar["address"] is None
