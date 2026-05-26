# backend/exporters/json_exporter.py
import json
from datetime import datetime, timezone
from pathlib import Path

from ..database.models import get_all_places
from slugify import slugify

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
BY_CITY_DIR = OUTPUT_DIR / "by_city"


def export_json() -> Path:
    """Exporta todos los lugares a output/places.json y output/by_city/*.json."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    BY_CITY_DIR.mkdir(exist_ok=True)

    places = get_all_places()
    places_dicts = [p.to_dict() for p in places]

    # Agrupar por ciudad (usando slug para nombre de archivo)
    by_city: dict = {}
    for p in places_dicts:
        city_slug = slugify(p["city"])
        by_city.setdefault(city_slug, []).append(p)

    # Archivos por ciudad
    for city_slug, city_places in by_city.items():
        city_path = BY_CITY_DIR / f"{city_slug}.json"
        city_data = {
            "metadata": {
                "city": city_places[0]["city"],
                "department": city_places[0]["department"],
                "exported_at": _now(),
                "total_places": len(city_places),
            },
            "places": city_places,
        }
        city_path.write_text(
            json.dumps(city_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Archivo principal
    main_path = OUTPUT_DIR / "places.json"
    main_data = {
        "metadata": {
            "exported_at": _now(),
            "total_places": len(places_dicts),
            "cities_covered": len(by_city),
            "categories": ["monuments", "nature", "viewpoints", "cultural"],
            "scraper_version": "1.0.0",
        },
        "places": places_dicts,
    }
    main_path.write_text(
        json.dumps(main_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return main_path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
