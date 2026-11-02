# backend/scraper/official_scraper.py
"""Recorrido de los municipios de Colombia buscando SOLO sitios públicos de
patrimonio cultural y turístico publicados por fuentes oficiales:

  1. Portal de la alcaldía (Mi Colombia Digital o HTML)        → alcaldia
  2. Portales de las gobernaciones y oficinas de turismo        → gobernacion / oficina_turismo
  3. Inventarios en datos.gov.co publicados por esas entidades  → datos_abiertos

Cada candidato pasa por ``heritage.evaluate`` (¿es un sitio público de
patrimonio?) y por ``geocode`` (¿dónde está, y está de verdad en ese
municipio?). Todo lo guardado conserva la URL oficial que lo respalda.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from slugify import slugify

from ..api.websocket import ConnectionManager
from ..config import config
from ..database.db import init_db
from ..database.models import (
    Place, count_places, get_pending_cities, init_city_progress,
    mark_city_complete, save_place,
)
from .cities import PRIORITY_DANE
from .municipalities import Municipality, by_dane, is_ambiguous_name, ordered
from .official.datos_abiertos import all_dataset_candidates
from .official.departmental import departmental_candidates
from .official.geocode import Geocoder, GeoResult, verify_official_coords
from .official.heritage import clean_name, evaluate
from .official.http import OfficialHttp
from .official.models import Candidate
from .official.portal import municipality_portal

logger = logging.getLogger(__name__)


def build_place(c: Candidate, m: Municipality, category: str,
                geo: Optional[GeoResult]) -> Place:
    name = clean_name(c.name)
    city_part = f"{m.name} {m.department}" if is_ambiguous_name(m) else m.name
    return Place(
        name=name,
        slug=slugify(f"{name} {city_part}"),
        city=m.name,
        department=m.department,
        category=category,
        description=c.description,
        address=c.address,
        latitude=geo.latitude if geo else None,
        longitude=geo.longitude if geo else None,
        main_image=c.image,
        phone=c.phone,
        email=c.email,
        source_url=c.source_url,
        dane_code=m.dane,
        source_type=c.source_type,
        source_entity=c.source_entity,
        evidence_url=c.evidence_url,
        geo_source=geo.source if geo else "",
        geo_distance_km=geo.distance_km if geo else None,
        geo_ref=geo.ref if geo else "",
        verified=geo is not None,
    )


async def verify_candidate(c: Candidate, m: Municipality,
                           geocoder: Optional[Geocoder]) -> tuple[Optional[Place], str]:
    """(Place, "") si el candidato es patrimonio público; (None, motivo) si no."""
    verdict = evaluate(
        c.name, c.description,
        type_hint=c.type_hint, ownership=c.ownership,
        heritage_source=c.heritage_source, municipality=m.name,
    )
    if not verdict.accepted:
        return None, verdict.reason
    geo = verify_official_coords(c.latitude, c.longitude, m, ref=c.evidence_url)
    if geo is None and geocoder is not None:
        geo = await geocoder.locate(clean_name(c.name), m)
    return build_place(c, m, verdict.category, geo), ""


async def scrape_all(manager: ConnectionManager, state=None):
    init_db()
    municipalities = ordered(PRIORITY_DANE)
    if config.only_dane_codes:
        wanted = set(config.only_dane_codes)
        municipalities = [m for m in municipalities if m.dane in wanted]
    init_city_progress([m.as_progress() for m in municipalities])
    wanted_codes = {m.dane for m in municipalities}
    pending = [p for p in get_pending_cities() if p["dane"] in wanted_codes]
    index = by_dane()

    await _log(manager, "info",
               f"Iniciando: {len(pending)} municipios pendientes · solo fuentes oficiales "
               f"(alcaldías, gobernaciones, oficinas de turismo, datos.gov.co)")

    start_time = datetime.now(timezone.utc)
    total_errors = 0

    async with OfficialHttp() as http, Geocoder() as geocoder:
        await _log(manager, "info", "Leyendo inventarios oficiales en datos.gov.co…")
        try:
            dataset_cands = await all_dataset_candidates(http)
        except Exception as e:
            dataset_cands = {}
            total_errors += 1
            await _log(manager, "error", f"Datos abiertos no disponibles: {str(e)[:100]}")
        await _log(manager, "info",
                   f"  {sum(len(v) for v in dataset_cands.values())} registros en "
                   f"{len(dataset_cands)} municipios")

        dept_cands: dict = {}
        if config.include_departmental:
            await _log(manager, "info", "Leyendo portales de gobernaciones y oficinas de turismo…")

            async def dept_log(msg: str):
                await _log(manager, "info", msg)

            try:
                dept_cands = await departmental_candidates(http, log=dept_log)
            except Exception as e:
                total_errors += 1
                await _log(manager, "error", f"Portales departamentales: {str(e)[:100]}")

        for i, row in enumerate(pending):
            if state and not state.running:
                await _log(manager, "info", "Scraping detenido por el usuario")
                break
            if state and state.paused:
                await _log(manager, "info", "Scraping pausado, esperando...")
                while state and state.paused and state.running:
                    await asyncio.sleep(1)
                if not state or not state.running:
                    break

            m = index.get(row["dane"])
            if m is None:
                continue
            if state:
                state.current_city = m.name
                state.cities_done = i
                state.cities_total = len(pending)

            await _log(manager, "info",
                       f"-> [{i + 1}/{len(pending)}] {m.name}, {m.department} (DANE {m.dane})")
            await manager.broadcast({
                "type": "progress",
                "citiesDone": i,
                "citiesTotal": len(pending),
                "placesFound": count_places(),
                "currentCity": m.name,
                "currentDepartment": m.department,
            })

            candidates: list[Candidate] = []
            if m.alcaldia_url:
                try:
                    found = await municipality_portal(http, m)
                    candidates.extend(found)
                    await _log(manager, "info",
                               f"  Alcaldía ({m.alcaldia_url}): {len(found)} fichas")
                except Exception as e:
                    total_errors += 1
                    await _log(manager, "warn", f"  Alcaldía: {str(e)[:100]}")
            else:
                await _log(manager, "warn", "  Sin portal oficial de alcaldía registrado")
            candidates.extend(dataset_cands.get(m.dane, []))
            candidates.extend(dept_cands.get(m.dane, []))

            new = dupes = rejected = unlocated = 0
            for c in candidates:
                if state and not state.running:
                    break
                try:
                    place, _reason = await verify_candidate(c, m, geocoder)
                except Exception as e:
                    total_errors += 1
                    await _log(manager, "warn", f"  Error verificando '{c.name[:40]}': {str(e)[:80]}")
                    continue
                if place is None:
                    rejected += 1
                    continue
                if not place.verified:
                    unlocated += 1
                if save_place(place):
                    new += 1
                    await manager.broadcast({"type": "place_found", "place": place.to_dict()})
                else:
                    dupes += 1
            if state:
                state.errors = total_errors

            mark_city_complete(m.dane, new)
            await _log(manager, "info",
                       f"✓ {m.name}: {new} sitios patrimoniales ({unlocated} sin ubicación "
                       f"verificada) · {rejected} descartados · {dupes} repetidos")
            await manager.broadcast({
                "type": "city_completed",
                "city": m.name,
                "placesCount": new,
                "duplicatesSkipped": dupes,
            })

    duration = int((datetime.now(timezone.utc) - start_time).total_seconds())
    total = count_places()
    await manager.broadcast({
        "type": "scrape_complete",
        "totalPlaces": total,
        "durationSeconds": duration,
        "errors": total_errors,
    })
    await _log(manager, "info",
               f"Scraping completado: {total} sitios oficiales "
               f"({count_places(verified_only=True)} con ubicación verificada) en {duration}s")


async def _log(manager: ConnectionManager, level: str, message: str):
    logger.info(message)
    await manager.broadcast({
        "type": "log",
        "level": level,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


class _ConsoleManager:
    """Para correr el scraper sin el dashboard: imprime los logs."""

    async def broadcast(self, message: dict):
        if message.get("type") == "log":
            print(message["message"], flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Scraper de patrimonio cultural y turístico desde fuentes oficiales")
    parser.add_argument("--solo", help="códigos DANE separados por coma (ej. 15407,68079)")
    parser.add_argument("--sin-gobernaciones", action="store_true",
                        help="no recorrer los portales departamentales")
    parser.add_argument("--sin-google", action="store_true",
                        help="no usar Google Maps como respaldo de ubicación")
    args = parser.parse_args()
    if args.solo:
        config.only_dane_codes = tuple(c.strip() for c in args.solo.split(",") if c.strip())
    if args.sin_gobernaciones:
        config.include_departmental = False
    if args.sin_google:
        config.geocoder_google_fallback = False
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(scrape_all(_ConsoleManager()))
