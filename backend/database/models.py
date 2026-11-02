# backend/database/models.py
import sqlite3
import uuid
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List

from slugify import slugify
from .db import get_db

logger = logging.getLogger(__name__)

# Campos que, si el registro ya existe, se completan con lo que aporte otra
# fuente oficial (sin pisar lo que ya había).
_MERGEABLE = ("description", "short_description", "address", "latitude", "longitude",
              "main_image", "phone", "email", "website", "geo_source",
              "geo_distance_km", "geo_ref")


@dataclass
class Place:
    name: str
    city: str
    department: str
    category: str
    description: str = ""
    short_description: Optional[str] = None
    address: str = ""
    country: str = "Colombia"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    main_image: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    scraped_at: str = ""
    source_url: Optional[str] = None
    id: str = ""
    slug: str = ""
    place_key: str = ""
    # ── Verificabilidad ────────────────────────────────────────────────────
    dane_code: str = ""            # municipio (DIVIPOLA)
    source_type: str = ""          # alcaldia | gobernacion | oficina_turismo | datos_abiertos
    source_entity: str = ""        # entidad pública que publica el sitio
    evidence_url: str = ""         # API/dataset con el registro exacto
    geo_source: str = ""           # fuente_oficial | openstreetmap | google_maps
    geo_distance_km: Optional[float] = None  # distancia a la cabecera municipal
    geo_ref: str = ""              # id OSM / Google / dataset
    verified: bool = False         # fuente oficial + ubicación verificada

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.slug:
            self.slug = slugify(f"{self.name} {self.city}")
        if not self.scraped_at:
            self.scraped_at = datetime.now(timezone.utc).isoformat()
        if self.description and not self.short_description:
            self.short_description = self.description[:160]
        # Identidad del lugar: municipio + nombre oficial; sin municipio, las
        # coordenadas redondeadas; si no, el slug.
        if not self.place_key:
            if self.dane_code:
                self.place_key = f"{self.dane_code}:{slugify(self.name)}"
            elif self.latitude is not None and self.longitude is not None:
                self.place_key = f"{self.latitude:.5f},{self.longitude:.5f}"
            else:
                self.place_key = self.slug

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "shortDescription": self.short_description,
            "address": self.address,
            "city": self.city,
            "citySlug": slugify(self.city),
            "department": self.department,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "mainImage": self.main_image,
            "phone": self.phone,
            "email": self.email,
            "website": self.website,
            "category": self.category,
            "scrapedAt": self.scraped_at,
            "sourceUrl": self.source_url,
            "daneCode": self.dane_code,
            "sourceType": self.source_type,
            "sourceEntity": self.source_entity,
            "evidenceUrl": self.evidence_url,
            "geoSource": self.geo_source,
            "geoDistanceKm": self.geo_distance_km,
            "verified": self.verified,
        }


def save_place(place: Place) -> bool:
    """Guarda un lugar. True si es nuevo; False si ya existía (en ese caso se
    completan los campos vacíos con lo que aporte este registro)."""
    city_slug = slugify(place.city)
    with get_db() as conn:
        try:
            conn.execute(
                """INSERT INTO places
                   (id, name, slug, description, short_description, address,
                    city, city_slug, department, country, latitude, longitude, main_image,
                    phone, email, website, category, scraped_at, source_url, place_key,
                    dane_code, source_type, source_entity, evidence_url, geo_source,
                    geo_distance_km, geo_ref, verified)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (place.id, place.name, place.slug, place.description,
                 place.short_description, place.address, place.city, city_slug,
                 place.department, place.country, place.latitude,
                 place.longitude, place.main_image, place.phone,
                 place.email, place.website, place.category,
                 place.scraped_at, place.source_url, place.place_key,
                 place.dane_code, place.source_type, place.source_entity,
                 place.evidence_url, place.geo_source, place.geo_distance_km,
                 place.geo_ref, int(place.verified)),
            )
            return True
        except sqlite3.IntegrityError:
            pass
    _merge_into_existing(place)
    return False


def _merge_into_existing(place: Place) -> None:
    sets = ", ".join(
        f"{col} = CASE WHEN {col} IS NULL OR {col} = '' THEN ? ELSE {col} END"
        for col in _MERGEABLE
    )
    values = [getattr(place, col) for col in _MERGEABLE]
    with get_db() as conn:
        conn.execute(
            f"""UPDATE places SET {sets},
                    verified = MAX(verified, ?)
                WHERE place_key = ? OR slug = ?""",
            (*values, int(place.verified), place.place_key, place.slug),
        )


_OFFICIAL = "source_type != ''"


def get_all_places(include_legacy: bool = False) -> List[Place]:
    """Lugares de fuentes oficiales. ``include_legacy`` incluye los que dejó la
    versión anterior del scraper (búsquedas en Google Maps, sin fuente oficial)."""
    where = "" if include_legacy else f"WHERE {_OFFICIAL}"
    with get_db() as conn:
        rows = conn.execute(f"SELECT * FROM places {where} ORDER BY city, name").fetchall()
        return [_row_to_place(r) for r in rows]


def get_places_by_city(city_slug: str) -> List[Place]:
    """Lugares de una ciudad por su slug (ej. 'bogota', 'medellin')."""
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM places WHERE city_slug = ? AND {_OFFICIAL} ORDER BY name",
            (city_slug,),
        ).fetchall()
        return [_row_to_place(r) for r in rows]


def get_places_paginated(page: int = 1, per_page: int = 50) -> tuple:
    """Retorna (places, total_count) para paginación."""
    offset = (page - 1) * per_page
    with get_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM places WHERE {_OFFICIAL}").fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM places WHERE {_OFFICIAL} ORDER BY city, name LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
    return [_row_to_place(r) for r in rows], total


def count_places(verified_only: bool = False) -> int:
    where = _OFFICIAL + (" AND verified = 1" if verified_only else "")
    with get_db() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM places WHERE {where}").fetchone()[0]


def count_legacy_places() -> int:
    with get_db() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM places WHERE NOT ({_OFFICIAL})").fetchone()[0]


def purge_legacy_places() -> int:
    """Borra los lugares sin fuente oficial (de la versión anterior)."""
    with get_db() as conn:
        cur = conn.execute(f"DELETE FROM places WHERE NOT ({_OFFICIAL})")
        return cur.rowcount


# ── Progreso por municipio (código DANE) ────────────────────────────────────

def init_city_progress(municipalities: list):
    """``municipalities``: dicts con ``dane``, ``name`` y ``department``."""
    with get_db() as conn:
        for m in municipalities:
            conn.execute(
                """INSERT OR IGNORE INTO city_progress
                   (city_slug, city_name, department, status)
                   VALUES (?, ?, ?, 'pending')""",
                (m["dane"], m["name"], m["department"]),
            )


def mark_city_complete(dane: str, places_count: int):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """UPDATE city_progress
               SET status='completed', places_found=?, completed_at=?
               WHERE city_slug=?""",
            (places_count, now, dane),
        )


def get_pending_cities() -> list:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT city_slug, city_name, department FROM city_progress "
            "WHERE status='pending' ORDER BY rowid"
        ).fetchall()
        return [{"dane": r["city_slug"], "name": r["city_name"], "department": r["department"]}
                for r in rows]


def get_city_progress() -> List[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT city_slug AS dane, city_name, department, status, places_found, completed_at "
            "FROM city_progress ORDER BY city_name"
        ).fetchall()
        return [dict(r) for r in rows]


def reset_city_progress():
    with get_db() as conn:
        conn.execute("UPDATE city_progress SET status='pending', places_found=0, completed_at=NULL")


def _row_to_place(row) -> Place:
    keys = row.keys()

    def col(name, default=None):
        return row[name] if name in keys else default

    return Place(
        id=row["id"],
        name=row["name"],
        slug=row["slug"],
        description=row["description"] or "",
        short_description=row["short_description"],
        address=row["address"] or "",
        city=row["city"],
        department=row["department"],
        country=row["country"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        main_image=row["main_image"],
        phone=row["phone"],
        email=row["email"],
        website=row["website"],
        category=row["category"],
        scraped_at=row["scraped_at"],
        source_url=row["source_url"],
        place_key=col("place_key") or "",
        dane_code=col("dane_code") or "",
        source_type=col("source_type") or "",
        source_entity=col("source_entity") or "",
        evidence_url=col("evidence_url") or "",
        geo_source=col("geo_source") or "",
        geo_distance_km=col("geo_distance_km"),
        geo_ref=col("geo_ref") or "",
        verified=bool(col("verified", 0)),
    )
