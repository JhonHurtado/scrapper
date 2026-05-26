# backend/database/models.py
import sqlite3
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from slugify import slugify
from .db import get_db


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

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.slug:
            self.slug = slugify(f"{self.name} {self.city}")
        if not self.scraped_at:
            self.scraped_at = datetime.now(timezone.utc).isoformat()
        if self.description and not self.short_description:
            self.short_description = self.description[:160]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "shortDescription": self.short_description,
            "address": self.address,
            "city": self.city,
            "department": self.department,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "mainImage": self.main_image,
            "phone": self.phone,
            "email": self.email,
            "website": self.website,
            "category": self.category,
        }


def save_place(place: Place) -> bool:
    """Guarda un lugar en DB. Retorna True si fue guardado, False si es duplicado."""
    with get_db() as conn:
        try:
            conn.execute(
                """INSERT INTO places
                   (id, name, slug, description, short_description, address,
                    city, department, country, latitude, longitude, main_image,
                    phone, email, website, category, scraped_at, source_url)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (place.id, place.name, place.slug, place.description,
                 place.short_description, place.address, place.city,
                 place.department, place.country, place.latitude,
                 place.longitude, place.main_image, place.phone,
                 place.email, place.website, place.category,
                 place.scraped_at, place.source_url),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def get_all_places() -> list:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM places ORDER BY city, name"
        ).fetchall()
        return [_row_to_place(r) for r in rows]


def get_places_by_city(city_slug: str) -> list:
    # Normalise the slug back to a searchable name, then compare by slug
    # to handle accented chars (e.g. "bogota" must match "Bogotá")
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM places WHERE lower(city) = lower(?) ORDER BY name",
            (city_slug.replace("-", " "),),
        ).fetchall()
        if rows:
            return [_row_to_place(r) for r in rows]
        # Fallback: compare via slugified city column
        all_rows = conn.execute(
            "SELECT * FROM places ORDER BY name"
        ).fetchall()
        return [
            _row_to_place(r) for r in all_rows
            if slugify(r["city"]) == city_slug
        ]


def count_places() -> int:
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM places").fetchone()[0]


def init_city_progress(cities: list):
    with get_db() as conn:
        for city in cities:
            conn.execute(
                """INSERT OR IGNORE INTO city_progress
                   (city_slug, city_name, department, status)
                   VALUES (?, ?, ?, 'pending')""",
                (slugify(city["name"]), city["name"], city["department"]),
            )


def mark_city_complete(city_name: str, department: str, places_count: int):
    slug = slugify(city_name)
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """UPDATE city_progress
               SET status='completed', places_found=?, completed_at=?
               WHERE city_slug=?""",
            (places_count, now, slug),
        )


def get_pending_cities() -> list:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT city_name, department FROM city_progress WHERE status='pending' ORDER BY rowid"
        ).fetchall()
        return [{"name": r["city_name"], "department": r["department"]} for r in rows]


def _row_to_place(row) -> Place:
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
    )
