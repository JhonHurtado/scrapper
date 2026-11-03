"""Ubicación verificada de un sitio oficial.

Las fuentes oficiales dicen QUÉ es patrimonio; casi nunca dicen DÓNDE con
coordenadas. Este módulo las obtiene y, sobre todo, las VERIFICA:

1. Coordenadas que trae la propia fuente (datasets) → se aceptan si caen
   dentro del radio del municipio (cabecera DANE).
2. OpenStreetMap (Nominatim) → se acepta un resultado solo si
   * su nombre se parece al nombre oficial (similitud por palabras), y
   * cae dentro del radio del municipio, y
   * si Nominatim dice en qué municipio está, es el nuestro.
3. Google Maps (Playwright), opcional, con las mismas reglas.

Sin ubicación verificada el sitio se guarda como no verificado y NO se exporta
al backend (que exige latitud/longitud).
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional
from urllib.parse import quote_plus

import httpx

from ...config import config
from ...database.db import get_db
from ..municipalities import Municipality, municipalities_of
from .browser import choose_browser
from .heritage import classify_name, normalize

logger = logging.getLogger(__name__)

GEO_OFFICIAL = "fuente_oficial"
GEO_OSM = "openstreetmap"
GEO_GOOGLE = "google_maps"

_STOP = {"de", "del", "la", "las", "el", "los", "y", "en", "a", "al", "san", "santa",
         "nuestra", "senora", "municipio", "municipal", "colombia"}


@dataclass
class GeoResult:
    latitude: float
    longitude: float
    source: str
    distance_km: float
    matched_name: str = ""
    ref: str = ""          # id OSM / place id de Google / dataset


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def max_km(m: Municipality) -> float:
    return config.geo_max_km_large if m.is_large else config.geo_max_km


def within_municipality(lat: float, lng: float, m: Municipality) -> Optional[float]:
    """Distancia a la cabecera si está dentro del radio permitido; None si no."""
    if m.lat is None or m.lng is None:
        return None
    d = haversine_km(lat, lng, m.lat, m.lng)
    return d if d <= max_km(m) else None


# Palabras de tipo de sitio: no distinguen un lugar de otro del mismo tipo.
_GENERIC = {
    "iglesia", "templo", "parroquia", "parroquial", "capilla", "catedral", "basilica",
    "santuario", "ermita", "museo", "casa", "parque", "plaza", "plazoleta", "plazuela",
    "puente", "monumento", "mirador", "cascada", "salto", "laguna", "lago", "cerro",
    "rio", "quebrada", "sitio", "centro", "cultural", "cultura", "historico", "historica",
    "antigua", "antiguo", "colonial", "arqueologico", "natural", "nacional",
}


def _tokens(text: str) -> list[str]:
    return [t for t in normalize(text).split() if t not in _STOP and len(t) > 1]


def name_similarity(official: str, found: str, ignore: Iterable[str] = ()) -> float:
    """0..1. Compara las palabras DISTINTIVAS (sin tipo de sitio ni nombre del
    municipio): "Templo Parroquial de N.S. del Rosario" ≈ "Iglesia de Nuestra
    Señora del Rosario", pero "…del Carmen" ≠ "…del Rosario". Si los dos nombres
    declaran tipos de sitio distintos (museo vs colegio) la similitud es 0."""
    a_all, b_all = _tokens(official), _tokens(found)
    if not a_all or not b_all:
        return 0.0
    cls_a, cls_b = classify_name(official), classify_name(found)
    if cls_a and cls_b and cls_a.category != cls_b.category:
        return 0.0
    skip = _GENERIC | set(ignore)
    a = {t for t in a_all if t not in skip}
    b = {t for t in b_all if t not in skip}
    if a and b:
        return len(a & b) / min(len(a), len(b))
    return SequenceMatcher(None, " ".join(sorted(a_all)), " ".join(sorted(b_all))).ratio()


def _municipality_tokens(m: Municipality) -> set[str]:
    return set(_tokens(m.name)) | set(_tokens(m.official_name))


# ── caché en SQLite (no repetir consultas entre corridas) ───────────────────

def _cache_get(key: str) -> Optional[list]:
    with get_db() as conn:
        row = conn.execute("SELECT payload FROM geocode_cache WHERE query = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def _cache_put(key: str, payload: list) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO geocode_cache (query, payload, created_at) VALUES (?, ?, ?)",
            (key, json.dumps(payload, ensure_ascii=False), time.time()),
        )


# ── reglas de aceptación ────────────────────────────────────────────────────

_MUNI_KEYS = ("municipality", "city", "town", "village", "county")


def _other_municipality(address: dict, m: Municipality) -> bool:
    """True si Nominatim ubica el resultado en OTRO municipio del departamento."""
    ours = {normalize(m.name), normalize(m.official_name)}
    named = {normalize(v) for k, v in (address or {}).items() if k in _MUNI_KEYS and v}
    if not named or named & ours:
        return False
    siblings = {normalize(x.name) for x in municipalities_of(m.department_code)} | \
               {normalize(x.official_name) for x in municipalities_of(m.department_code)}
    return bool(named & (siblings - ours))


def pick_nominatim(results: list[dict], name: str, m: Municipality) -> Optional[GeoResult]:
    best: Optional[tuple[float, GeoResult]] = None
    for r in results:
        try:
            lat, lng = float(r["lat"]), float(r["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        dist = within_municipality(lat, lng, m)
        if dist is None or _other_municipality(r.get("address") or {}, m):
            continue
        found_name = r.get("name") or (r.get("display_name") or "").split(",")[0]
        score = name_similarity(name, found_name, _municipality_tokens(m))
        if score < config.geo_min_name_similarity:
            continue
        ref = f"osm:{r.get('osm_type', '')}/{r.get('osm_id', '')}"
        candidate = GeoResult(lat, lng, GEO_OSM, round(dist, 2), found_name, ref)
        if best is None or score > best[0]:
            best = (score, candidate)
    return best[1] if best else None


# ── geocodificadores ────────────────────────────────────────────────────────

class Geocoder:
    """Nominatim (+ Google Maps opcional). Usar como context manager."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()
        self._last = 0.0
        self._google: Optional["_GoogleMaps"] = None

    async def __aenter__(self) -> "Geocoder":
        self._client = httpx.AsyncClient(
            headers={"User-Agent": config.http_user_agent, "Accept-Language": "es"},
            timeout=config.http_timeout,
        )
        if config.geocoder_google_fallback:
            self._google = _GoogleMaps()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client:
            await self._client.aclose()
        if self._google:
            await self._google.close()

    async def _nominatim(self, query: str) -> list[dict]:
        key = f"nominatim:{query}"
        cached = _cache_get(key)
        if cached is not None:
            return cached
        async with self._lock:  # política de uso: ≤ 1 petición por segundo
            wait = config.nominatim_delay - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
            try:
                r = await self._client.get(config.nominatim_url, params={
                    "q": query, "format": "jsonv2", "addressdetails": 1,
                    "limit": 5, "countrycodes": "co",
                })
            except httpx.HTTPError as e:
                logger.info("Nominatim no respondió: %s", e)
                return []
        if r.status_code != 200:
            logger.info("Nominatim respondió %s", r.status_code)
            return []
        results = r.json()
        _cache_put(key, results)
        return results

    async def locate(self, name: str, m: Municipality) -> Optional[GeoResult]:
        query = f"{name}, {m.name}, {m.department}, Colombia"
        found = pick_nominatim(await self._nominatim(query), name, m)
        if found is None and self._google is not None:
            found = await self._google.locate(name, m)
        return found


def verify_official_coords(lat: Optional[float], lng: Optional[float],
                           m: Municipality, ref: str = "") -> Optional[GeoResult]:
    if lat is None or lng is None:
        return None
    dist = within_municipality(lat, lng, m)
    if dist is None:
        return None
    return GeoResult(lat, lng, GEO_OFFICIAL, round(dist, 2), ref=ref)


# ── Google Maps (Playwright), solo como respaldo ────────────────────────────

def extract_place_coords(href: str) -> tuple[Optional[float], Optional[float]]:
    """Coordenadas del lugar desde un enlace de Google Maps (!3d<lat>!4d<lng>)."""
    match = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", href or "")
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None


def extract_google_place_id(href: str) -> Optional[str]:
    match = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", href or "")
    return match.group(1) if match else None


def clean_text(text: Optional[str]) -> str:
    """Quita glifos de iconos (área de uso privado Unicode) y espacios."""
    return re.sub(r"[\ue000-\uf8ff]", "", text or "").strip()


class _GoogleMaps:
    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._failed = False

    async def _ensure(self) -> bool:
        if self._context is not None:
            return True
        if self._failed:
            return False
        choice = choose_browser()
        if choice.note:
            logger.warning(choice.note)
        if not choice.enabled:
            self._failed = True
            return False
        try:
            from playwright.async_api import async_playwright
            self._pw = await async_playwright().start()
            launch = {"headless": config.headless}
            if choice.executable:
                # Brave/Chrome/Edge instalados: no hace falta descargar Chromium.
                launch["executable_path"] = choice.executable
            self._browser = await self._pw.chromium.launch(**launch)
            self._context = await self._browser.new_context(locale="es-CO")
            logger.info("Respaldo de Google Maps con %s", choice.label)
            return True
        except Exception as e:
            logger.warning("Google Maps no disponible como respaldo (%s): %s", choice.label, e)
            self._failed = True
            return False

    async def locate(self, name: str, m: Municipality) -> Optional[GeoResult]:
        key = f"google:{name}|{m.dane}"
        cached = _cache_get(key)
        if cached is None:
            cached = await self._search(f"{name}, {m.name}, {m.department}, Colombia")
            _cache_put(key, cached)
        best: Optional[tuple[float, GeoResult]] = None
        for item in cached:
            lat, lng = item.get("lat"), item.get("lng")
            if lat is None or lng is None:
                continue
            dist = within_municipality(lat, lng, m)
            score = name_similarity(name, item.get("name", ""), _municipality_tokens(m))
            if dist is None or score < config.geo_min_name_similarity:
                continue
            res = GeoResult(lat, lng, GEO_GOOGLE, round(dist, 2), item.get("name", ""),
                            f"google:{item.get('place_id') or ''}")
            if best is None or score > best[0]:
                best = (score, res)
        return best[1] if best else None

    async def _search(self, query: str) -> list[dict]:
        if not await self._ensure():
            return []
        page = await self._context.new_page()
        try:
            url = f"https://www.google.com/maps/search/{quote_plus(query)}"
            await page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            await asyncio.sleep(2.5)
            if await page.locator("form#captcha-form").count() > 0:
                logger.warning("Google Maps pidió verificación; se omite el respaldo")
                self._failed = True
                return []
            results = []
            # Resultado único: Google abre directamente la ficha del lugar.
            if "/maps/place/" in page.url:
                title = page.locator("h1").first
                name = clean_text(await title.text_content()) if await title.count() else ""
                lat, lng = extract_place_coords(page.url)
                if lat is None:
                    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", page.url)
                    lat, lng = (float(m.group(1)), float(m.group(2))) if m else (None, None)
                results.append({"name": name, "lat": lat, "lng": lng,
                                "place_id": extract_google_place_id(page.url)})
            for link in (await page.locator("a.hfpxzc").all())[:5]:
                href = await link.get_attribute("href") or ""
                lat, lng = extract_place_coords(href)
                results.append({"name": clean_text(await link.get_attribute("aria-label")),
                                "lat": lat, "lng": lng,
                                "place_id": extract_google_place_id(href)})
            return results
        except Exception as e:
            logger.info("Google Maps falló para %r: %s", query, e)
            return []
        finally:
            await page.close()

    async def close(self) -> None:
        try:
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
