# tests/test_official_sources.py
"""Pruebas del flujo de fuentes oficiales sin red (httpx.MockTransport)."""
import json

import httpx
import pytest

from backend.scraper.official.heritage import evaluate


# ── Clasificación patrimonial ───────────────────────────────────────────────

@pytest.mark.parametrize("name,text,category", [
    ("TEMPLO PARROQUIAL DE NUESTRA SEÑORA DEL ROSARIO", "", "iglesias"),
    ("Casa Museo Antonio Nariño", "", "museos"),
    ("Parque Arqueológico de Monquirá", "", "sitios_arqueologicos"),
    ("Plaza de Mercado de Paloquemao", "", "mercados"),
    ("Parque Nacional Natural Chingaza", "", "reservas_naturales"),
    ("Puente de Occidente", "", "puentes"),
    ("La Piedra del Peñol", "", "cerros_y_montanas"),
    ("Casa de la Cultura de Salamina", "", "centros_culturales"),
    ("Molino de la Primavera", "Edificación colonial de 1630", "sitios_culturales"),
])
def test_accepts_public_heritage_sites(name, text, category):
    verdict = evaluate(name, text, municipality="Villa de Leyva")
    assert verdict.accepted, verdict.reason
    assert verdict.category == category


@pytest.mark.parametrize("name,reason", [
    ("Hotel Dinastía Descanso y Armonía", "negocio privado"),
    ("Glamping Las Estrellas", "negocio privado"),
    ("Parque Temático Los Dinosaurios", "negocio privado"),
    ("Autorizan intervención de la capilla de la Iglesia", "el nombre no empieza por un tipo de sitio"),
    ("Sitios de Interés", "encabezado genérico"),
    ("Iglesia", "nombre genérico (una sola palabra)"),
    ("Villa de Leyva Monumento Nacional", "habla del municipio, no de un sitio"),
    ("Termales de Santa Rosa", "categoría excluida (termales)"),
    ("Casa de Rosa María Saleme", "tipo ambiguo sin evidencia patrimonial"),
])
def test_rejects_private_generic_or_non_heritage(name, reason):
    verdict = evaluate(name, "", municipality="Villa de Leyva")
    assert not verdict.accepted
    assert verdict.reason == reason


def test_private_ownership_declared_by_source_is_rejected():
    assert not evaluate("Iglesia San Juan", ownership="Privada").accepted
    assert evaluate("Iglesia San Juan", ownership="Pública").accepted


def test_heritage_inventory_counts_as_evidence():
    assert evaluate("Casa de Rosa María Saleme", heritage_source=True).accepted


def test_type_hint_classifies_names_without_head_noun():
    verdict = evaluate("Universidad Nacional", type_hint="Los Monumentos Nacionales",
                       heritage_source=True)
    assert verdict.accepted and verdict.category == "monumentos"


# ── Extracción HTML ─────────────────────────────────────────────────────────

SHAREPOINT_PAGE = """
<html><body><form id="aspnetForm">
<div id="menu-principal"><a href="/">Inicio</a><a href="/turismo">Turismo</a></div>
<div id="DeltaPlaceHolderMain">
 <div class="ms-rtestate-field"><h1>Sitios de Interés</h1></div>
 <div class="ms-rtestate-field">
  <div><span><strong>TEMPLO PARROQUIAL DE NUESTRA SEÑORA DEL ROSARIO</strong></span></div>
  <img src="/img/templo.jpg">
  <div><span>Fue construido en 1604, de tipo barroco colonial.</span></div>
 </div>
 <div class="ms-rtestate-field">
  <div><strong>HOTEL PLAZA</strong></div><p>Habitaciones desde $100.000</p>
 </div>
 <div class="ms-rtestate-field">
  <div><b>CASA MUSEO ANTONIO NARIÑO</b></div>
  <p>Declarada Monumento Nacional en 1961. Dirección: Carrera 9 Nº 10-25 Tel: (8) 732 0342</p>
 </div>
</div></form></body></html>
"""


def test_extract_blocks_from_sharepoint_template():
    from backend.scraper.official.html_extract import extract_blocks
    blocks = extract_blocks(SHAREPOINT_PAGE, "https://www.villadeleyva-boyaca.gov.co/p.aspx")
    titles = [b.title for b in blocks]
    assert "TEMPLO PARROQUIAL DE NUESTRA SEÑORA DEL ROSARIO" in titles
    templo = blocks[titles.index("TEMPLO PARROQUIAL DE NUESTRA SEÑORA DEL ROSARIO")]
    assert "1604" in templo.text
    assert templo.image == "https://www.villadeleyva-boyaca.gov.co/img/templo.jpg"


def test_tourism_links_stay_on_official_site():
    from backend.scraper.official.html_extract import tourism_links
    html = """<a href="/MiMunicipio/Paginas/Sitios-de-Interes.aspx">Sitios de interés</a>
              <a href="https://www.tripadvisor.com/turismo">Turismo</a>
              <a href="/noticias/turismo-2024">Noticia de turismo</a>
              <a href="/MiMunicipio/Paginas/Directorio-Turistico.aspx">Directorio turístico</a>"""
    links = tourism_links(html, "https://www.x-boyaca.gov.co/")
    assert links == ["https://www.x-boyaca.gov.co/MiMunicipio/Paginas/Sitios-de-Interes.aspx"]


# ── HTTP: solo dominios oficiales ───────────────────────────────────────────

def test_is_official_url():
    from backend.scraper.official.http import is_official_url
    assert is_official_url("https://www.barichara-santander.gov.co/turismo")
    assert is_official_url("https://baricharasantander.micolombiadigital.gov.co/api/v1/config")
    assert is_official_url("https://www.datos.gov.co/resource/x.json")
    assert not is_official_url("https://www.google.com/maps")
    assert not is_official_url("https://gov.co.evil.com/x")
    assert not is_official_url("ftp://www.x.gov.co")


@pytest.fixture
def no_delays(monkeypatch):
    from backend.config import config
    monkeypatch.setattr(config, "http_host_delay", 0)
    monkeypatch.setattr(config, "respect_robots", False)
    monkeypatch.setattr(config, "max_retries", 1)


def _http(handler):
    from backend.scraper.official.http import OfficialHttp
    return OfficialHttp(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_http_refuses_non_official_urls(no_delays):
    from backend.scraper.official.http import NotOfficialError
    async with _http(lambda r: httpx.Response(200)) as http:
        with pytest.raises(NotOfficialError):
            await http.get("https://www.tripadvisor.com/x")


async def test_http_does_not_follow_redirect_out_of_gov(no_delays):
    def handler(request):
        if request.url.host == "www.x.gov.co":
            return httpx.Response(302, headers={"location": "https://spam.example.com/"})
        return httpx.Response(200, text="spam")
    from backend.scraper.official.http import OfficialHttp
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    async with OfficialHttp(client) as http:
        assert await http.get("https://www.x.gov.co/") is None


async def test_http_stops_on_access_denied(no_delays):
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(403)
    async with _http(handler) as http:
        r = await http.get("https://www.bloqueado.gov.co/a")
        assert r.status == 403
        assert await http.get("https://www.bloqueado.gov.co/b") is None
    assert len(calls) == 1  # no se insiste ni se intenta evadir


# ── Mi Colombia Digital ─────────────────────────────────────────────────────

BASE = "http://www.pueblo-boyaca.gov.co"
API = "https://pueblo.micolombiadigital.gov.co"


def _mcd_handler(request: httpx.Request) -> httpx.Response:
    path, params = request.url.path, dict(request.url.params)
    if request.url.host == "www.pueblo-boyaca.gov.co" and path == "/api/v1/config":
        return httpx.Response(200, json={
            "authorityDomain": API,
            "resources": {"Header.Title": "Alcaldía Municipal de Pueblo, Boyacá"},
        })
    if path == "/api/v1/menufind":
        if params.get("KeyWord") == "turismo":
            return httpx.Response(200, json=[{"tagID": 34, "name": "Turismo"}])
        return httpx.Response(200, json=[])
    if path == "/api/v1/tags/34":
        return httpx.Response(200, json={"tagID": 34, "friendlyName": "turismo"})
    if path == "/api/v1/contents" and params.get("tags") == "34":
        if params.get("page") != "0":
            return httpx.Response(200, json={"meta": {"hasNextPage": False}, "results": []})
        return httpx.Response(200, json={"meta": {"hasNextPage": False}, "results": [
            {"friendlyName": "iglesia-de-santa-barbara", "name": "Iglesia de Santa Bárbara",
             "contentType": "Article", "metaDescription": "Dirección: Calle 5"},
            {"friendlyName": "hotel-colonial", "name": "Hotel Colonial",
             "contentType": "Article", "metaDescription": ""},
        ]})
    if path == "/api/v1/contents":
        return httpx.Response(200, json={"meta": {"hasNextPage": False}, "results": []})
    if path == "/api/v1/contents/iglesia-de-santa-barbara":
        return httpx.Response(200, json={
            "name": "Iglesia de Santa Bárbara",
            "body": "<p>Templo colonial del siglo XVII.</p><p>Dirección: Calle 5 # 3-20</p>"
                    "<p>Teléfono: 7321234</p>",
            "defaultImage": f"{API}/sites/pueblo/content/files/iglesia.jpg",
            "tags": [{"tagID": 34, "friendlyName": "turismo"}],
        })
    return httpx.Response(404)


async def test_mcd_reads_tourism_section_from_api(no_delays):
    from backend.scraper.official import mcd
    async with _http(_mcd_handler) as http:
        site = await mcd.detect(http, BASE)
        assert site.api == API
        found = await mcd.candidates(http, site, "Pueblo")
    assert [c.name for c in found] == ["Iglesia de Santa Bárbara"]  # el hotel no
    c = found[0]
    assert c.source_url == f"{BASE}/turismo/iglesia-de-santa-barbara"
    assert c.evidence_url == f"{API}/api/v1/contents/iglesia-de-santa-barbara"
    assert c.description == "Templo colonial del siglo XVII."
    assert c.address == "Calle 5 # 3-20"
    assert c.phone == "7321234"
    assert c.image.endswith("iglesia.jpg")


# ── Datos abiertos ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("5º26'14.20\"N 72º26'58.03\"W", (5.437278, -72.449453)),
    ("3°32′00″N 75°57′00″O", (3.533333, -75.95)),
    ("9.228000  -75.818400", (9.228, -75.8184)),
    ("4.278028, -74.761917", (4.278028, -74.761917)),
    ({"type": "Point", "coordinates": [-75.687, 4.860]}, (4.86, -75.687)),
    ({"latitude": "5.43728", "longitude": "-72.449455"}, (5.43728, -72.449455)),
    ("4.240.987", (None, None)),
    ("10.9, -84.75", (None, None)),  # Costa Rica
])
def test_parse_coordinates(value, expected):
    from backend.scraper.official.datos_abiertos import parse_coordinates
    lat, lng = parse_coordinates(value)
    if expected[0] is None:
        assert (lat, lng) == (None, None)
    else:
        assert lat == pytest.approx(expected[0], abs=1e-5)
        assert lng == pytest.approx(expected[1], abs=1e-5)


async def test_dataset_rows_are_filtered_and_attributed(no_delays):
    from backend.scraper.official.datos_abiertos import dataset_candidates
    rows = [
        {"sitio": "Laguna la Macolla", "municipio": "Paz de Ariporo", "tipo": "Natural",
         "ubicaci_n": {"latitude": "5.88", "longitude": "-71.89"}},
        {"sitio": "Festival del Pastel", "municipio": "Yopal", "tipo": "Gastronómico"},
        {"sitio": "Iglesia de Nunchía", "municipio": "Municipio Inexistente", "tipo": "Religioso"},
    ]

    def handler(request):
        assert request.url.path == "/resource/abcd-1234.json"
        return httpx.Response(200, json=rows)
    spec = {"id": "abcd-1234", "entidad": "Gobernación de Casanare", "departamento": "85",
            "campos": {"nombre": "sitio", "municipio": "municipio", "tipo": "tipo",
                       "coordenadas": "ubicaci_n"},
            "tipos_permitidos": ["Natural", "Religioso"]}
    async with _http(handler) as http:
        pairs = await dataset_candidates(http, spec)
    assert len(pairs) == 1
    municipality, c = pairs[0]
    assert municipality.dane == "85250"
    assert (c.latitude, c.longitude) == (5.88, -71.89)
    assert c.source_url == "https://www.datos.gov.co/d/abcd-1234"
    assert c.source_type == "datos_abiertos"


# ── Ubicación verificada ────────────────────────────────────────────────────

def _villa_de_leyva():
    from backend.scraper.municipalities import by_dane
    return by_dane()["15407"]


def test_nominatim_result_must_match_name_and_municipality():
    from backend.scraper.official.geocode import pick_nominatim
    m = _villa_de_leyva()
    results = [
        # mismo nombre pero en otro municipio del departamento → fuera
        {"lat": "5.53", "lon": "-73.36", "name": "Casa Museo Antonio Nariño",
         "address": {"city": "Tunja"}, "osm_type": "node", "osm_id": 1},
        # dentro del municipio pero nombre distinto → fuera
        {"lat": "5.633", "lon": "-73.525", "name": "Panadería La Villa",
         "address": {"town": "Villa de Leyva"}, "osm_type": "node", "osm_id": 2},
        {"lat": "5.6320868", "lon": "-73.5249697", "name": "Casa museo Antonio Narino",
         "address": {"town": "Villa de Leiva", "county": "Villa de Leyva"},
         "osm_type": "node", "osm_id": 5742284521},
    ]
    geo = pick_nominatim(results, "CASA MUSEO ANTONIO NARIÑO", m)
    assert geo.ref == "osm:node/5742284521"
    assert geo.source == "openstreetmap"
    assert geo.distance_km < 1


def test_official_coords_outside_municipality_are_not_trusted():
    from backend.scraper.official.geocode import verify_official_coords
    m = _villa_de_leyva()
    assert verify_official_coords(5.6325, -73.5249, m).source == "fuente_oficial"
    assert verify_official_coords(11.24, -74.21, m) is None  # Santa Marta


def test_name_similarity_tolerates_wording():
    from backend.scraper.official.geocode import name_similarity
    assert name_similarity("Templo Parroquial de Nuestra Señora del Rosario",
                           "Iglesia de Nuestra Señora del Rosario") >= 0.6
    assert name_similarity("Iglesia de San Francisco", "Hotel Boutique Leyva") < 0.6
    assert name_similarity("Iglesia Nuestra Señora del Carmen",
                           "Iglesia Nuestra Señora del Rosario") < 0.6
    assert name_similarity("Casa Museo Antonio Nariño", "Colegio Antonio Nariño") == 0


class _FakeGeocoder:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    async def locate(self, name, m):
        self.calls.append(name)
        return self.result


async def test_verify_candidate_builds_traceable_place():
    from backend.scraper.official.geocode import GeoResult
    from backend.scraper.official.models import Candidate
    from backend.scraper.official_scraper import verify_candidate
    m = _villa_de_leyva()
    c = Candidate(name="CASA MUSEO ANTONIO NARIÑO", description="Monumento Nacional.",
                  source_url="https://www.villadeleyva-boyaca.gov.co/sitios",
                  source_entity="Alcaldía de Villa de Leyva (Boyacá)", source_type="alcaldia")
    geocoder = _FakeGeocoder(GeoResult(5.632, -73.525, "openstreetmap", 0.1, ref="osm:node/1"))
    place, reason = await verify_candidate(c, m, geocoder)
    assert reason == ""
    assert place.name == "Casa Museo Antonio Nariño"
    assert place.category == "museos"
    assert place.dane_code == "15407" and place.city == "Villa de Leyva"
    assert place.verified and place.geo_ref == "osm:node/1"
    assert place.source_url == "https://www.villadeleyva-boyaca.gov.co/sitios"


async def test_verify_candidate_keeps_unlocated_site_as_unverified():
    from backend.scraper.official.models import Candidate
    from backend.scraper.official_scraper import verify_candidate
    c = Candidate(name="Puente de Calicanto", source_url="https://www.x.gov.co",
                  source_entity="Alcaldía", source_type="alcaldia")
    place, _ = await verify_candidate(c, _villa_de_leyva(), _FakeGeocoder(None))
    assert place is not None and not place.verified and place.latitude is None


async def test_verify_candidate_rejects_business_without_geocoding():
    from backend.scraper.official.models import Candidate
    from backend.scraper.official_scraper import verify_candidate
    geocoder = _FakeGeocoder(None)
    c = Candidate(name="Hostal La Candelaria", source_url="https://www.x.gov.co",
                  source_entity="Alcaldía", source_type="alcaldia")
    place, reason = await verify_candidate(c, _villa_de_leyva(), geocoder)
    assert place is None and reason == "negocio privado"
    assert geocoder.calls == []


def test_registry_is_valid_and_official():
    from backend.scraper.municipalities import by_dane
    from backend.scraper.official.datos_abiertos import load_registry
    from backend.scraper.official.http import is_official_url
    registry = load_registry()
    for spec in registry["datasets"]:
        assert spec["id"] and spec["entidad"] and spec["campos"]["nombre"]
        assert spec.get("dane") in by_dane() or spec.get("departamento")
    for page in registry["paginas_turismo"]:
        assert is_official_url(page["url"])
    json.dumps(registry)


# ── Portal HTML (plantilla SharePoint) ──────────────────────────────────────

async def test_html_portal_reads_tourism_pages_not_the_home(no_delays):
    from backend.scraper.official.portal import portal_candidates
    home = """<html><body><div id="DeltaPlaceHolderMain">
      <h2>Biblioteca Pública Municipal</h2><p>Noticia de la portada.</p>
      <a href="/MiMunicipio/Paginas/Sitios-de-Interes.aspx">Sitios de Interés</a>
    </div></body></html>"""

    def handler(request):
        path = request.url.path
        if path == "/":
            return httpx.Response(302, headers={"location": "/Paginas/Inicio.aspx"})
        if path == "/Paginas/Inicio.aspx":
            return httpx.Response(200, text=home, headers={"content-type": "text/html"})
        if path == "/MiMunicipio/Paginas/Sitios-de-Interes.aspx":
            return httpx.Response(200, text=SHAREPOINT_PAGE,
                                  headers={"content-type": "text/html; charset=utf-8"})
        return httpx.Response(404)

    from backend.scraper.official.http import OfficialHttp
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    async with OfficialHttp(client) as http:
        found = await portal_candidates(http, "https://www.pueblo-boyaca.gov.co",
                                        entity="Alcaldía de Pueblo (Boyacá)",
                                        source_type="alcaldia", municipality="Pueblo")
    names = {c.name for c in found}
    assert "Biblioteca Pública Municipal" not in names
    assert "CASA MUSEO ANTONIO NARIÑO" in names
    museo = next(c for c in found if c.name == "CASA MUSEO ANTONIO NARIÑO")
    assert museo.source_url == "https://www.pueblo-boyaca.gov.co/MiMunicipio/Paginas/Sitios-de-Interes.aspx"
    assert museo.address == "Carrera 9 Nº 10-25"
    assert museo.source_entity == "Alcaldía de Pueblo (Boyacá)"
