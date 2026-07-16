# backend/exporters/prisma_exporter.py
"""Transforma los lugares scrapeados en seed data para el schema Prisma (Place/Category)."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import List

from ..database.models import Place, get_all_places

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
PRISMA_DIR = OUTPUT_DIR / "prisma"

CATEGORIES = {
    "monuments":  {"name": "Monumentos e Historia", "slug": "monumentos",
                   "icon": "landmark", "label": "monumento histórico"},
    "nature":     {"name": "Naturaleza", "slug": "naturaleza",
                   "icon": "leaf", "label": "atractivo natural"},
    "viewpoints": {"name": "Miradores y Paisajes", "slug": "miradores",
                   "icon": "mountain", "label": "mirador"},
    "cultural":   {"name": "Cultura", "slug": "cultura",
                   "icon": "masks-theater", "label": "sitio cultural"},
}

# Caja delimitadora de Colombia (incluye San Andrés/Providencia y Amazonas)
LAT_RANGE = (-4.5, 14.0)
LNG_RANGE = (-82.0, -66.0)
# ponytail: filtro de outliers por mediana de ciudad; si hace falta más precisión,
# usar centroides oficiales DANE por municipio
MAX_KM_FROM_CITY = 60.0
MIN_CITY_SAMPLE = 3

# Negocios que no son sitios turísticos pero aparecen en las búsquedas
_EXCLUDE_NAME = ("agencia de turismo", "agencia de viajes", "tour operador",
                 "operador turístico", "travel agency")


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def build_seed_data(places: List[Place]) -> dict:
    """Filtra y normaliza lugares para cumplir el schema Prisma:
    lat/lng no nulos y dentro de Colombia, sin outliers lejanos a su ciudad,
    description y address nunca vacíos."""
    valid = [
        p for p in places
        if p.latitude is not None and p.longitude is not None
        and LAT_RANGE[0] <= p.latitude <= LAT_RANGE[1]
        and LNG_RANGE[0] <= p.longitude <= LNG_RANGE[1]
        and not any(x in p.name.lower() for x in _EXCLUDE_NAME)
    ]

    by_city: dict = {}
    for p in valid:
        by_city.setdefault(p.city, []).append(p)

    kept: List[Place] = []
    dropped_outliers = 0
    for city_places in by_city.values():
        if len(city_places) >= MIN_CITY_SAMPLE:
            med_lat = median(p.latitude for p in city_places)
            med_lng = median(p.longitude for p in city_places)
            for p in city_places:
                if _haversine_km(p.latitude, p.longitude, med_lat, med_lng) <= MAX_KM_FROM_CITY:
                    kept.append(p)
                else:
                    dropped_outliers += 1
        else:
            kept.extend(city_places)

    out_places = []
    for p in sorted(kept, key=lambda x: (x.department, x.city, x.name)):
        cat = CATEGORIES.get(p.category, CATEGORIES["cultural"])
        description = p.description.strip() or (
            f"{p.name}, {cat['label']} en {p.city}, {p.department}, Colombia."
        )
        out_places.append({
            "name": p.name,
            "slug": p.slug,
            "description": description,
            "shortDescription": (p.short_description or description)[:160],
            "address": p.address.strip() or f"{p.city}, {p.department}, Colombia",
            "city": p.city,
            "department": p.department,
            "country": p.country,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "mainImage": p.main_image,
            "phone": p.phone,
            "email": p.email,
            "website": p.website,
            "category": p.category,
        })

    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_places": len(out_places),
            "cities": len({p["city"] for p in out_places}),
            "departments": len({p["department"] for p in out_places}),
            "dropped_no_coords": len(places) - len(valid),
            "dropped_outliers": dropped_outliers,
        },
        "categories": [
            {"name": c["name"], "slug": c["slug"], "icon": c["icon"], "key": key}
            for key, c in CATEGORIES.items()
        ],
        "places": out_places,
    }


def export_prisma() -> Path:
    """Escribe output/prisma/seed-data.json listo para consumir desde prisma/seed.ts."""
    PRISMA_DIR.mkdir(parents=True, exist_ok=True)
    data = build_seed_data(get_all_places())
    path = PRISMA_DIR / "seed-data.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(export_prisma())
