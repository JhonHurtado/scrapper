# backend/exporters/prisma_exporter.py
"""Genera el catálogo con el formato EXACTO que consume el backend
(backend-cityscout-2.0/prisma/data/places.json → ``npm run seed:places``):

    {
      "metadata":   {..., "total_kept": N, "categories": {"iglesias": 12, ...}},
      "categories": {"iglesias": [LugarOrigen, ...], "museos": [...], ...}
    }

Solo entran sitios con fuente oficial Y ubicación verificada (el backend exige
latitud/longitud). Cada lugar lleva además ``sourceUrl``/``sourceEntity`` para
poder auditarlo; el seed del backend ignora los campos que no conoce.
"""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from ..database.models import Place, get_all_places
from ..scraper.official.heritage import BACKEND_CATEGORIES, EXCLUDED_CATEGORIES

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
PRISMA_DIR = OUTPUT_DIR / "prisma"

# Caja delimitadora de Colombia (incluye San Andrés/Providencia y Amazonas)
LAT_RANGE = (-4.5, 14.0)
LNG_RANGE = (-82.0, -66.0)


def _in_colombia(p: Place) -> bool:
    return (p.latitude is not None and p.longitude is not None
            and LAT_RANGE[0] <= p.latitude <= LAT_RANGE[1]
            and LNG_RANGE[0] <= p.longitude <= LNG_RANGE[1])


def _exclusion_reason(p: Place) -> str:
    if not p.source_type:
        return "sin_fuente_oficial"
    if not p.verified:
        return "sin_ubicacion_verificada"
    if not _in_colombia(p):
        return "fuera_de_colombia"
    if p.category not in BACKEND_CATEGORIES or p.category in EXCLUDED_CATEGORIES:
        return "categoria_no_patrimonial"
    return ""


def _lugar(p: Place) -> dict:
    description = p.description.strip()
    return {
        "name": p.name,
        "slug": p.slug,
        # El seed del backend genera "<nombre>, en <ciudad> (<depto>)." si viene
        # vacía: no se inventa ninguna descripción aquí.
        "description": description or None,
        "shortDescription": (p.short_description or description)[:160] or None,
        "address": p.address.strip() or None,
        "city": p.city,
        "department": p.department,
        "country": p.country,
        "latitude": p.latitude,
        "longitude": p.longitude,
        "mainImage": p.main_image,
        "phone": p.phone,
        "email": p.email,
        "website": p.website,
        # Trazabilidad (el seed del backend ignora estos campos)
        "sourceUrl": p.source_url,
        "sourceEntity": p.source_entity,
        "sourceType": p.source_type,
        "evidenceUrl": p.evidence_url or None,
        "daneCode": p.dane_code,
        "geoSource": p.geo_source,
        "geoDistanceKm": p.geo_distance_km,
    }


def build_seed_data(places: List[Place]) -> dict:
    kept: dict = {}
    excluded: Counter = Counter()
    for p in sorted(places, key=lambda x: (x.department, x.city, x.name)):
        reason = _exclusion_reason(p)
        if reason:
            excluded[reason] += 1
            continue
        kept.setdefault(p.category, []).append(_lugar(p))

    counts = dict(sorted(((k, len(v)) for k, v in kept.items()), key=lambda kv: -kv[1]))
    total_kept = sum(counts.values())
    by_source = Counter(item["sourceType"] for items in kept.values() for item in items)
    return {
        "metadata": {
            "source": "scraper de fuentes oficiales (alcaldías, gobernaciones, "
                      "oficinas de turismo y datos.gov.co)",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_original": len(places),
            "total_kept": total_kept,
            "total_excluded": len(places) - total_kept,
            "excluded_reasons": dict(excluded),
            "sources": dict(by_source),
            "categories": counts,
        },
        "categories": {k: kept[k] for k in counts},
    }


def export_prisma() -> Path:
    """Escribe output/prisma/places.json, listo para copiar a
    backend-cityscout-2.0/prisma/data/places.json."""
    PRISMA_DIR.mkdir(parents=True, exist_ok=True)
    data = build_seed_data(get_all_places())
    path = PRISMA_DIR / "places.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(export_prisma())
