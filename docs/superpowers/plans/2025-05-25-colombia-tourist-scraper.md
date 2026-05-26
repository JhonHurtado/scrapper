# Colombia Tourist Places Scraper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python/FastAPI scraper that extrae datos de lugares turísticos de Google Maps en 130 ciudades colombianas y los transmite en tiempo real a un dashboard React Split-View vía WebSockets, exportando a JSON.

**Architecture:** FastAPI monolito corre el scraper Playwright como asyncio background task, emite eventos WebSocket, y persiste en SQLite. React frontend (Vite + TypeScript) renderiza Split View de logs + tarjetas de lugares en tiempo real.

**Tech Stack:** Python 3.11+, FastAPI, Playwright, SQLite (stdlib), python-slugify, React 18, Vite 5, TypeScript 5

---

## File Map

```
scrapper/
├── backend/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app + uvicorn entry point
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── playwright_scraper.py      # Lógica principal de scraping con Playwright
│   │   ├── cities.py                  # Lista de 130 ciudades con departamento
│   │   └── queries.py                 # Búsquedas por categoría
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py                  # REST endpoints + ScrapeState
│   │   └── websocket.py               # ConnectionManager (broadcast WebSocket)
│   ├── database/
│   │   ├── __init__.py
│   │   ├── db.py                      # SQLite init + context manager
│   │   └── models.py                  # Place dataclass + CRUD functions
│   └── exporters/
│       ├── __init__.py
│       └── json_exporter.py           # Genera places.json + by_city/*.json
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css
│       ├── types/
│       │   └── index.ts               # Place, LogEntry, ScrapingStats
│       ├── hooks/
│       │   └── useWebSocket.ts        # WebSocket hook con auto-reconexión
│       └── components/
│           ├── StatsBar.tsx           # KPIs + controles Start/Pause/Stop/Export
│           ├── LogPanel.tsx           # Panel izquierdo: logs coloreados
│           ├── PlacesPanel.tsx        # Panel derecho: tarjetas animadas
│           └── PlaceCard.tsx          # Tarjeta individual de lugar
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_exporter.py
│   └── test_routes.py
├── output/
│   └── by_city/                       # Auto-creado por json_exporter
├── requirements.txt
├── pytest.ini
├── run.sh
├── .gitignore
└── README.md
```

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.gitignore`
- Create: `backend/__init__.py`
- Create: `backend/scraper/__init__.py`
- Create: `backend/api/__init__.py`
- Create: `backend/database/__init__.py`
- Create: `backend/exporters/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Inicializar git y crear estructura de directorios**

```bash
cd /Users/jhon/Desarrollo/personal/programacion/scrapper
git init
mkdir -p backend/scraper backend/api backend/database backend/exporters
mkdir -p tests output/by_city
mkdir -p frontend/src/types frontend/src/hooks frontend/src/components
touch backend/__init__.py backend/scraper/__init__.py backend/api/__init__.py
touch backend/database/__init__.py backend/exporters/__init__.py
touch tests/__init__.py
```

- [ ] **Step 2: Crear requirements.txt**

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
playwright>=1.44.0
python-slugify>=8.0.4
aiofiles>=23.2.1
pytest>=8.2.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
```

- [ ] **Step 3: Crear pytest.ini**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 4: Crear .gitignore**

```
__pycache__/
*.pyc
.venv/
venv/
*.db
output/
node_modules/
frontend/dist/
.superpowers/
.env
```

- [ ] **Step 5: Instalar dependencias Python**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Expected: `✓ Chromium` en la salida de playwright install.

- [ ] **Step 6: Commit inicial**

```bash
git add .
git commit -m "chore: project scaffolding — structure, requirements, gitignore"
```

---

## Task 2: Database layer — db.py + models.py

**Files:**
- Create: `backend/database/db.py`
- Create: `backend/database/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Escribir tests que fallan**

```python
# tests/test_models.py
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("backend.database.db.DB_PATH", db_file)
    from backend.database.db import init_db
    init_db()
    return db_file


def test_save_and_retrieve_place(tmp_db):
    from backend.database.models import Place, save_place, get_all_places
    p = Place(name="Plaza de Bolívar", city="Bogotá", department="Cundinamarca", category="monuments")
    assert save_place(p) is True
    places = get_all_places()
    assert len(places) == 1
    assert places[0].name == "Plaza de Bolívar"
    assert places[0].slug == "plaza-de-bolivar-bogota"


def test_duplicate_slug_returns_false(tmp_db):
    from backend.database.models import Place, save_place
    p1 = Place(name="Plaza de Bolívar", city="Bogotá", department="Cundinamarca", category="monuments")
    p2 = Place(name="Plaza de Bolívar", city="Bogotá", department="Cundinamarca", category="cultural")
    assert save_place(p1) is True
    assert save_place(p2) is False  # mismo slug


def test_place_to_dict_uses_camel_case(tmp_db):
    from backend.database.models import Place
    p = Place(name="Cerro", city="Cali", department="Valle del Cauca", category="viewpoints",
              main_image="https://img.example.com/cerro.jpg")
    d = p.to_dict()
    assert "mainImage" in d
    assert "shortDescription" in d
    assert "main_image" not in d


def test_short_description_auto_generated(tmp_db):
    from backend.database.models import Place
    long_desc = "A" * 200
    p = Place(name="X", city="Y", department="Z", category="nature", description=long_desc)
    assert len(p.short_description) == 160


def test_count_places(tmp_db):
    from backend.database.models import Place, save_place, count_places
    assert count_places() == 0
    save_place(Place(name="Lugar A", city="Bogotá", department="Cundinamarca", category="nature"))
    assert count_places() == 1


def test_get_places_by_city(tmp_db):
    from backend.database.models import Place, save_place, get_places_by_city
    save_place(Place(name="Lugar A", city="Bogotá", department="Cundinamarca", category="nature"))
    save_place(Place(name="Lugar B", city="Medellín", department="Antioquia", category="cultural"))
    bogota = get_places_by_city("bogota")
    assert len(bogota) == 1
    assert bogota[0].city == "Bogotá"


def test_city_progress_flow(tmp_db):
    from backend.database.models import init_city_progress, get_pending_cities, mark_city_complete
    cities = [{"name": "Bogotá", "department": "Cundinamarca"},
              {"name": "Medellín", "department": "Antioquia"}]
    init_city_progress(cities)
    pending = get_pending_cities()
    assert len(pending) == 2
    mark_city_complete("Bogotá", "Cundinamarca", 15)
    pending_after = get_pending_cities()
    assert len(pending_after) == 1
    assert pending_after[0]["name"] == "Medellín"
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError` o `ImportError` (los módulos no existen aún).

- [ ] **Step 3: Implementar backend/database/db.py**

```python
# backend/database/db.py
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS places (
                id               TEXT PRIMARY KEY,
                name             TEXT NOT NULL,
                slug             TEXT UNIQUE NOT NULL,
                description      TEXT NOT NULL DEFAULT '',
                short_description TEXT,
                address          TEXT NOT NULL DEFAULT '',
                city             TEXT NOT NULL,
                department       TEXT NOT NULL,
                country          TEXT NOT NULL DEFAULT 'Colombia',
                latitude         REAL,
                longitude        REAL,
                main_image       TEXT,
                phone            TEXT,
                email            TEXT,
                website          TEXT,
                category         TEXT NOT NULL,
                scraped_at       TEXT NOT NULL,
                source_url       TEXT
            );

            CREATE TABLE IF NOT EXISTS scrape_sessions (
                id               TEXT PRIMARY KEY,
                started_at       TEXT NOT NULL,
                completed_at     TEXT,
                cities_processed INTEGER DEFAULT 0,
                total_places     INTEGER DEFAULT 0,
                status           TEXT DEFAULT 'running'
            );

            CREATE TABLE IF NOT EXISTS city_progress (
                city_slug    TEXT PRIMARY KEY,
                city_name    TEXT NOT NULL,
                department   TEXT NOT NULL,
                status       TEXT DEFAULT 'pending',
                places_found INTEGER DEFAULT 0,
                completed_at TEXT
            );
        """)
```

- [ ] **Step 4: Implementar backend/database/models.py**

```python
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


def get_all_places() -> list[Place]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM places ORDER BY city, name"
        ).fetchall()
        return [_row_to_place(r) for r in rows]


def get_places_by_city(city_slug: str) -> list[Place]:
    city_name = city_slug.replace("-", " ")
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM places WHERE lower(city) = lower(?) ORDER BY name",
            (city_name,),
        ).fetchall()
        return [_row_to_place(r) for r in rows]


def count_places() -> int:
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM places").fetchone()[0]


def init_city_progress(cities: list[dict]):
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


def get_pending_cities() -> list[dict]:
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
```

- [ ] **Step 5: Correr tests y verificar que pasan**

```bash
pytest tests/test_models.py -v
```

Expected: `7 passed` en verde.

- [ ] **Step 6: Commit**

```bash
git add backend/database/ tests/test_models.py
git commit -m "feat: database layer — SQLite init, Place model, CRUD functions"
```

---

## Task 3: Cities list + search queries

**Files:**
- Create: `backend/scraper/cities.py`
- Create: `backend/scraper/queries.py`
- Create: `tests/test_cities.py`

- [ ] **Step 1: Escribir tests que fallan**

```python
# tests/test_cities.py
from backend.scraper.cities import CITIES
from backend.scraper.queries import CATEGORY_QUERIES, build_queries_for_city


def test_cities_list_has_minimum_count():
    assert len(CITIES) >= 60


def test_all_cities_have_name_and_department():
    for city in CITIES:
        assert "name" in city and city["name"]
        assert "department" in city and city["department"]


def test_category_queries_has_four_categories():
    assert set(CATEGORY_QUERIES.keys()) == {"monuments", "nature", "viewpoints", "cultural"}


def test_build_queries_for_city_substitutes_city_name():
    queries = build_queries_for_city("Bogotá")
    assert any("Bogotá" in q["query"] for q in queries)
    assert all("category" in q for q in queries)


def test_build_queries_returns_all_categories():
    queries = build_queries_for_city("Cali")
    categories = {q["category"] for q in queries}
    assert categories == {"monuments", "nature", "viewpoints", "cultural"}
```

- [ ] **Step 2: Verificar que fallan**

```bash
pytest tests/test_cities.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar backend/scraper/cities.py**

```python
# backend/scraper/cities.py

CITIES = [
    # ── Capitales departamentales (32) ──────────────────────────────────
    {"name": "Bogotá",                  "department": "Cundinamarca"},
    {"name": "Medellín",                "department": "Antioquia"},
    {"name": "Cali",                    "department": "Valle del Cauca"},
    {"name": "Barranquilla",            "department": "Atlántico"},
    {"name": "Cartagena",               "department": "Bolívar"},
    {"name": "Cúcuta",                  "department": "Norte de Santander"},
    {"name": "Bucaramanga",             "department": "Santander"},
    {"name": "Pereira",                 "department": "Risaralda"},
    {"name": "Santa Marta",             "department": "Magdalena"},
    {"name": "Ibagué",                  "department": "Tolima"},
    {"name": "Manizales",               "department": "Caldas"},
    {"name": "Pasto",                   "department": "Nariño"},
    {"name": "Neiva",                   "department": "Huila"},
    {"name": "Villavicencio",           "department": "Meta"},
    {"name": "Armenia",                 "department": "Quindío"},
    {"name": "Valledupar",              "department": "Cesar"},
    {"name": "Montería",                "department": "Córdoba"},
    {"name": "Sincelejo",               "department": "Sucre"},
    {"name": "Popayán",                 "department": "Cauca"},
    {"name": "Florencia",               "department": "Caquetá"},
    {"name": "Quibdó",                  "department": "Chocó"},
    {"name": "Tunja",                   "department": "Boyacá"},
    {"name": "Riohacha",                "department": "La Guajira"},
    {"name": "San Andrés",              "department": "San Andrés y Providencia"},
    {"name": "Yopal",                   "department": "Casanare"},
    {"name": "Mocoa",                   "department": "Putumayo"},
    {"name": "Inírida",                 "department": "Guainía"},
    {"name": "Mitú",                    "department": "Vaupés"},
    {"name": "Puerto Carreño",          "department": "Vichada"},
    {"name": "San José del Guaviare",   "department": "Guaviare"},
    {"name": "Leticia",                 "department": "Amazonas"},
    {"name": "Arauca",                  "department": "Arauca"},
    # ── Ciudades intermedias importantes ────────────────────────────────
    {"name": "Palmira",                 "department": "Valle del Cauca"},
    {"name": "Buenaventura",            "department": "Valle del Cauca"},
    {"name": "Bello",                   "department": "Antioquia"},
    {"name": "Envigado",                "department": "Antioquia"},
    {"name": "Rionegro",                "department": "Antioquia"},
    {"name": "Soledad",                 "department": "Atlántico"},
    {"name": "Soacha",                  "department": "Cundinamarca"},
    {"name": "Girardot",                "department": "Cundinamarca"},
    {"name": "Dosquebradas",            "department": "Risaralda"},
    {"name": "Tuluá",                   "department": "Valle del Cauca"},
    {"name": "Floridablanca",           "department": "Santander"},
    {"name": "Barrancabermeja",         "department": "Santander"},
    {"name": "Sogamoso",                "department": "Boyacá"},
    {"name": "Duitama",                 "department": "Boyacá"},
    {"name": "Espinal",                 "department": "Tolima"},
    {"name": "Maicao",                  "department": "La Guajira"},
    {"name": "Magangué",                "department": "Bolívar"},
    {"name": "Lorica",                  "department": "Córdoba"},
    # ── Pueblos Patrimonio de Colombia ──────────────────────────────────
    {"name": "Mompox",                  "department": "Bolívar"},
    {"name": "Villa de Leyva",          "department": "Boyacá"},
    {"name": "Barichara",               "department": "Santander"},
    {"name": "Salento",                 "department": "Quindío"},
    {"name": "Guaduas",                 "department": "Cundinamarca"},
    {"name": "Honda",                   "department": "Tolima"},
    {"name": "Jardín",                  "department": "Antioquia"},
    {"name": "Jericó",                  "department": "Antioquia"},
    {"name": "Concepción",              "department": "Antioquia"},
    {"name": "Támesis",                 "department": "Antioquia"},
    {"name": "Aguadas",                 "department": "Caldas"},
    {"name": "Salamina",                "department": "Caldas"},
    {"name": "Neira",                   "department": "Caldas"},
    {"name": "Filadelfia",              "department": "Caldas"},
    {"name": "Marsella",                "department": "Risaralda"},
    {"name": "Filandia",                "department": "Quindío"},
    {"name": "Ráquira",                 "department": "Boyacá"},
    {"name": "Monguí",                  "department": "Boyacá"},
    {"name": "Tibasosa",                "department": "Boyacá"},
    {"name": "Sutamarchán",             "department": "Boyacá"},
    {"name": "Vélez",                   "department": "Santander"},
    {"name": "Playa de Belén",          "department": "Norte de Santander"},
    {"name": "San Agustín",             "department": "Huila"},
    {"name": "La Plata",                "department": "Huila"},
    {"name": "Isnos",                   "department": "Huila"},
    {"name": "Ciénaga",                 "department": "Magdalena"},
    {"name": "El Banco",                "department": "Magdalena"},
    {"name": "Manaure",                 "department": "La Guajira"},
    {"name": "Providencia",             "department": "San Andrés y Providencia"},
    {"name": "Bahía Solano",            "department": "Chocó"},
    {"name": "Nuquí",                   "department": "Chocó"},
]
```

- [ ] **Step 4: Implementar backend/scraper/queries.py**

```python
# backend/scraper/queries.py

CATEGORY_QUERIES: dict[str, list[str]] = {
    "monuments": [
        "monumentos históricos en {city}",
        "iglesias patrimonio en {city}",
        "sitios arqueológicos en {city}",
    ],
    "nature": [
        "parques naturales en {city}",
        "cascadas cerca de {city}",
        "senderos ecoturismo {city}",
    ],
    "viewpoints": [
        "miradores en {city}",
        "malecón de {city}",
        "playas y lagunas cerca de {city}",
    ],
    "cultural": [
        "barrios típicos de {city}",
        "mercados artesanales en {city}",
        "turismo cultural {city}",
    ],
}


def build_queries_for_city(city_name: str) -> list[dict]:
    """Retorna lista de {query, category} para una ciudad."""
    result = []
    for category, templates in CATEGORY_QUERIES.items():
        for template in templates:
            result.append({
                "query": template.format(city=city_name),
                "category": category,
            })
    return result
```

- [ ] **Step 5: Correr tests**

```bash
pytest tests/test_cities.py -v
```

Expected: `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/scraper/cities.py backend/scraper/queries.py tests/test_cities.py
git commit -m "feat: cities list (80 locations) + category search queries"
```

---

## Task 4: JSON Exporter

**Files:**
- Create: `backend/exporters/json_exporter.py`
- Create: `tests/test_exporter.py`

- [ ] **Step 1: Escribir tests que fallan**

```python
# tests/test_exporter.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def setup_db_with_places(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.database.db.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("backend.exporters.json_exporter.OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr("backend.exporters.json_exporter.BY_CITY_DIR", tmp_path / "output" / "by_city")
    from backend.database.db import init_db
    from backend.database.models import Place, save_place
    init_db()
    save_place(Place(name="Plaza de Bolívar", city="Bogotá",
                     department="Cundinamarca", category="monuments",
                     description="Plaza histórica"))
    save_place(Place(name="Cerro de Monserrate", city="Bogotá",
                     department="Cundinamarca", category="viewpoints"))
    save_place(Place(name="El Peñol", city="Guatapé",
                     department="Antioquia", category="nature"))
    return tmp_path


def test_export_creates_main_json(setup_db_with_places):
    from backend.exporters.json_exporter import export_json
    path = export_json()
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["metadata"]["total_places"] == 3
    assert len(data["places"]) == 3


def test_export_creates_by_city_files(setup_db_with_places):
    from backend.exporters.json_exporter import export_json, BY_CITY_DIR
    export_json()
    bogota_file = BY_CITY_DIR / "bogota.json"
    assert bogota_file.exists()
    data = json.loads(bogota_file.read_text(encoding="utf-8"))
    assert data["metadata"]["total_places"] == 2


def test_export_uses_camel_case_keys(setup_db_with_places):
    from backend.exporters.json_exporter import export_json
    path = export_json()
    data = json.loads(path.read_text(encoding="utf-8"))
    place = data["places"][0]
    assert "shortDescription" in place
    assert "mainImage" in place
    assert "short_description" not in place
```

- [ ] **Step 2: Verificar que fallan**

```bash
pytest tests/test_exporter.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar backend/exporters/json_exporter.py**

```python
# backend/exporters/json_exporter.py
import json
from datetime import datetime, timezone
from pathlib import Path

from ..database.models import get_all_places

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
BY_CITY_DIR = OUTPUT_DIR / "by_city"


def export_json() -> Path:
    """Exporta todos los lugares a output/places.json y output/by_city/*.json."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    BY_CITY_DIR.mkdir(exist_ok=True)

    places = get_all_places()
    places_dicts = [p.to_dict() for p in places]

    # Agrupar por ciudad
    by_city: dict[str, list[dict]] = {}
    for p in places_dicts:
        city_slug = p["city"].lower().replace(" ", "-")
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
```

- [ ] **Step 4: Correr tests**

```bash
pytest tests/test_exporter.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/exporters/json_exporter.py tests/test_exporter.py
git commit -m "feat: JSON exporter — places.json + per-city files"
```

---

## Task 5: WebSocket manager

**Files:**
- Create: `backend/api/websocket.py`

- [ ] **Step 1: Implementar backend/api/websocket.py**

```python
# backend/api/websocket.py
import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WS connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WS disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Envía un mensaje JSON a todos los clientes conectados."""
        if not self.active_connections:
            return
        data = json.dumps(message, ensure_ascii=False, default=str)
        dead: list[WebSocket] = []
        for conn in self.active_connections:
            try:
                await conn.send_text(data)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)


manager = ConnectionManager()
```

- [ ] **Step 2: Smoke test manual del manager**

```python
# Ejecuta esto en un Python REPL para verificar la clase:
from backend.api.websocket import ConnectionManager
mgr = ConnectionManager()
assert len(mgr.active_connections) == 0
print("ConnectionManager OK")
```

```bash
python -c "from backend.api.websocket import ConnectionManager; m=ConnectionManager(); print('OK', len(m.active_connections))"
```

Expected: `OK 0`

- [ ] **Step 3: Commit**

```bash
git add backend/api/websocket.py
git commit -m "feat: WebSocket ConnectionManager with broadcast + dead-connection cleanup"
```

---

## Task 6: Scraping state + REST routes

**Files:**
- Create: `backend/api/routes.py`
- Create: `tests/test_routes.py`

- [ ] **Step 1: Escribir tests que fallan**

```python
# tests/test_routes.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.database.db.DB_PATH", tmp_path / "test.db")
    from backend.database.db import init_db
    init_db()
    from backend.main import app
    return TestClient(app)


def test_scrape_status_idle(client):
    r = client.get("/api/scrape/status")
    assert r.status_code == 200
    data = r.json()
    assert data["running"] is False
    assert "places" in data


def test_list_places_empty(client):
    r = client.get("/api/places")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_list_places_pagination(client, tmp_path, monkeypatch):
    monkeypatch.setattr("backend.database.db.DB_PATH", tmp_path / "test.db")
    from backend.database.db import init_db
    from backend.database.models import Place, save_place
    init_db()
    for i in range(5):
        save_place(Place(name=f"Lugar {i}", city="Bogotá",
                         department="Cundinamarca", category="nature"))
    from backend.main import app
    c = TestClient(app)
    r = c.get("/api/places?page=1&per_page=3")
    data = r.json()
    assert data["total"] == 5
    assert len(data["places"]) == 3


def test_websocket_connects(client):
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert "session_id" in msg
```

- [ ] **Step 2: Verificar que fallan**

```bash
pytest tests/test_routes.py -v
```

Expected: `ModuleNotFoundError` (main.py no existe aún).

- [ ] **Step 3: Implementar backend/api/routes.py**

```python
# backend/api/routes.py
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse

from ..database.models import get_all_places, count_places
from ..exporters.json_exporter import export_json, OUTPUT_DIR
from .websocket import manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@dataclass
class ScrapeState:
    running: bool = False
    paused: bool = False
    current_city: str = ""
    cities_done: int = 0
    cities_total: int = 0
    errors: int = 0


state = ScrapeState()


@router.post("/scrape/start")
async def start_scrape(background_tasks: BackgroundTasks):
    if state.running:
        return {"status": "already_running"}
    state.running = True
    state.paused = False
    background_tasks.add_task(_run_scrape)
    return {"status": "started"}


async def _run_scrape():
    from ..scraper.playwright_scraper import scrape_all
    try:
        await scrape_all(manager, state)
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        await manager.broadcast({"type": "error", "message": str(e)})
    finally:
        state.running = False
        state.paused = False


@router.post("/scrape/pause")
async def pause_scrape():
    """Pausa al terminar la ciudad actual (no interrumpe mid-scraping)."""
    state.paused = True
    return {"status": "pausing"}


@router.post("/scrape/resume")
async def resume_scrape():
    state.paused = False
    return {"status": "resumed"}


@router.post("/scrape/stop")
async def stop_scrape():
    state.running = False
    state.paused = False
    return {"status": "stopped"}


@router.get("/scrape/status")
async def scrape_status():
    return {
        "running": state.running,
        "paused": state.paused,
        "current_city": state.current_city,
        "cities_done": state.cities_done,
        "cities_total": state.cities_total,
        "places": count_places(),
        "errors": state.errors,
    }


@router.get("/export/json")
async def export_places():
    path = export_json()
    return FileResponse(
        path=str(path),
        filename="places.json",
        media_type="application/json",
    )


@router.get("/places")
async def list_places(page: int = 1, per_page: int = 50):
    all_places = get_all_places()
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "total": len(all_places),
        "page": page,
        "per_page": per_page,
        "places": [p.to_dict() for p in all_places[start:end]],
    }
```

- [ ] **Step 4: Crear backend/main.py (mínimo para tests)**

```python
# backend/main.py
import uuid
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .database.db import init_db
from .api.routes import router
from .api.websocket import manager

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Colombia Tourist Scraper", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def startup():
    init_db()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    session_id = str(uuid.uuid4())
    await manager.broadcast({"type": "connected", "session_id": session_id})
    try:
        while True:
            await websocket.receive_text()  # mantener conexión viva (ping)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

- [ ] **Step 5: Correr tests**

```bash
pytest tests/test_routes.py -v
```

Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes.py backend/main.py tests/test_routes.py
git commit -m "feat: REST routes + ScrapeState + FastAPI app entry point"
```

---

## Task 7: Playwright scraper

**Files:**
- Create: `backend/scraper/playwright_scraper.py`

*Nota: Este módulo no tiene unit tests automatizados (requiere navegador real). Se verifica manualmente con `--test-city`.*

- [ ] **Step 1: Implementar backend/scraper/playwright_scraper.py**

```python
# backend/scraper/playwright_scraper.py
import asyncio
import logging
import random
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright, BrowserContext, Page

from ..api.websocket import ConnectionManager
from ..database.db import init_db
from ..database.models import (
    Place, count_places, init_city_progress,
    get_pending_cities, mark_city_complete, save_place,
)
from .cities import CITIES
from .queries import build_queries_for_city

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


async def scrape_all(manager: ConnectionManager, state=None):
    """Entry point principal. Scrapea todas las ciudades pendientes."""
    init_db()
    init_city_progress(CITIES)
    pending = get_pending_cities()

    await _log(manager, "info",
               f"Iniciando scraping: {len(pending)} ciudades pendientes")

    start_time = datetime.now(timezone.utc)
    total_errors = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": random.randint(1366, 1920), "height": 900},
            locale="es-CO",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for i, city in enumerate(pending):
            # Verificar si debe detenerse
            if state and not state.running:
                await _log(manager, "info", "⏹ Scraping detenido por el usuario")
                break

            city_name = city["name"]
            department = city["department"]

            if state:
                state.current_city = city_name
                state.cities_done = i

            await _log(manager, "info",
                       f"→ Ciudad [{i + 1}/{len(pending)}]: {city_name}, {department}")
            await manager.broadcast({
                "type": "progress",
                "cities_done": i,
                "cities_total": len(pending),
                "places_found": count_places(),
                "current_city": city_name,
                "current_department": department,
            })

            city_places = 0
            city_dupes = 0

            for item in build_queries_for_city(city_name):
                query = item["query"]
                category = item["category"]

                await _log(manager, "info", f'  Búsqueda: "{query}"')

                places, errors = await _scrape_query(
                    context, query, city_name, department, category, manager
                )
                total_errors += errors

                for place in places:
                    saved = save_place(place)
                    if saved:
                        city_places += 1
                        await manager.broadcast({
                            "type": "place_found",
                            "place": place.to_dict(),
                        })
                    else:
                        city_dupes += 1

                await asyncio.sleep(random.uniform(2.0, 4.0))

            mark_city_complete(city_name, department, city_places)
            await _log(manager, "info",
                       f"✓ {city_name} completada → {city_places} lugares"
                       f" ({city_dupes} dupl. omitidos)")
            await manager.broadcast({
                "type": "city_completed",
                "city": city_name,
                "places_count": city_places,
                "duplicates_skipped": city_dupes,
            })

            # Esperar si está pausado (termina ciudad actual antes de pausar)
            if state:
                while state.paused and state.running:
                    await asyncio.sleep(1)

            await asyncio.sleep(random.uniform(3.0, 6.0))

        await browser.close()

    duration = int((datetime.now(timezone.utc) - start_time).total_seconds())
    total = count_places()
    await manager.broadcast({
        "type": "scrape_complete",
        "total_places": total,
        "duration_seconds": duration,
        "errors": total_errors,
    })
    await _log(manager, "info",
               f"✅ Scraping completado: {total} lugares en {duration}s")


async def _scrape_query(
    context: BrowserContext,
    query: str,
    city: str,
    department: str,
    category: str,
    manager: ConnectionManager,
) -> tuple[list[Place], int]:
    """Busca una query en Google Maps y retorna los lugares encontrados."""
    page = await context.new_page()
    places: list[Place] = []
    errors = 0

    try:
        url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(2)

        # Detectar CAPTCHA
        if await page.locator("form#captcha-form").count() > 0:
            await _log(manager, "warn",
                       f"⚠ reCAPTCHA detectado — esperando 60s...")
            await asyncio.sleep(60)
            await page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(3)

        # Scroll para cargar más resultados
        feed = page.locator('div[role="feed"]')
        if await feed.count() == 0:
            return places, errors

        for _ in range(3):
            await feed.evaluate("el => el.scrollTo(0, el.scrollHeight)")
            await asyncio.sleep(1.5)

        items = await page.locator(".Nv2PK").all()
        found_count = 0

        for item in items[:20]:
            try:
                await item.click()
                await asyncio.sleep(1.8)

                place = await _extract_place(page, city, department, category)
                if place:
                    places.append(place)
                    found_count += 1

            except Exception as e:
                errors += 1
                await _log(manager, "warn",
                           f"  ⚠ Error extrayendo lugar: {str(e)[:80]}")
                continue

        if found_count:
            await _log(manager, "info", f"  ✦ {found_count} lugares encontrados")

    except Exception as e:
        errors += 1
        await _log(manager, "error",
                   f"  ✗ Error en búsqueda '{query}': {str(e)[:100]}")
    finally:
        await page.close()

    return places, errors


async def _extract_place(
    page: Page, city: str, department: str, category: str
) -> Place | None:
    """Extrae datos del panel lateral de un lugar en Google Maps."""
    try:
        # Nombre
        name_locator = page.locator("h1").first
        if await name_locator.count() == 0:
            return None
        name = (await name_locator.text_content(timeout=5_000) or "").strip()
        if not name:
            return None

        # Coordenadas desde la URL
        lat, lng = _extract_coords(page.url)

        # Dirección
        address = ""
        addr = page.locator('button[data-item-id="address"]').first
        if await addr.count() > 0:
            address = (await addr.text_content() or "").strip()

        # Teléfono
        phone = None
        phone_el = page.locator('button[data-item-id="phone"]').first
        if await phone_el.count() > 0:
            phone = (await phone_el.text_content() or "").strip() or None

        # Sitio web
        website = None
        web_el = page.locator('a[data-item-id="authority"]').first
        if await web_el.count() > 0:
            website = await web_el.get_attribute("href")

        # Imagen principal
        main_image = None
        img = page.locator('button[jsaction*="heroHeaderImage"] img').first
        if await img.count() > 0:
            main_image = await img.get_attribute("src")

        # Descripción (sección "Acerca de" o editorial)
        description = ""
        desc_el = page.locator(".PYvSYb, [data-attrid='description'] span").first
        if await desc_el.count() > 0:
            description = (await desc_el.text_content() or "").strip()

        return Place(
            name=name,
            city=city,
            department=department,
            category=category,
            description=description,
            address=address,
            latitude=lat,
            longitude=lng,
            main_image=main_image,
            phone=phone,
            website=website,
            source_url=page.url,
        )

    except Exception:
        return None


def _extract_coords(url: str) -> tuple[float | None, float | None]:
    match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None


async def _log(manager: ConnectionManager, level: str, message: str):
    logger.info(message)
    await manager.broadcast({
        "type": "log",
        "level": level,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
```

- [ ] **Step 2: Verificar que el módulo importa correctamente**

```bash
python -c "from backend.scraper.playwright_scraper import scrape_all; print('Import OK')"
```

Expected: `Import OK`

- [ ] **Step 3: Test de extracción de coordenadas (unitario)**

```python
# Agregar a tests/test_models.py
def test_extract_coords_from_url():
    from backend.scraper.playwright_scraper import _extract_coords
    url = "https://www.google.com/maps/place/Plaza/@4.5981,-74.0759,17z/data=..."
    lat, lng = _extract_coords(url)
    assert lat == 4.5981
    assert lng == -74.0759

def test_extract_coords_missing():
    from backend.scraper.playwright_scraper import _extract_coords
    lat, lng = _extract_coords("https://www.google.com/maps/search/bogota")
    assert lat is None
    assert lng is None
```

```bash
pytest tests/test_models.py -v -k "coords"
```

Expected: `2 passed`.

- [ ] **Step 4: Commit**

```bash
git add backend/scraper/playwright_scraper.py tests/test_models.py
git commit -m "feat: Playwright scraper — Google Maps extraction with anti-detection"
```

---

## Task 8: Frontend scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`

- [ ] **Step 1: Crear frontend/package.json**

```json
{
  "name": "colombia-tourist-scraper-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.4.5",
    "vite": "^5.3.1"
  }
}
```

- [ ] **Step 2: Crear frontend/tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Crear frontend/vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        rewriteWsOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 4: Crear frontend/index.html**

```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Colombia Tourist Scraper</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Crear frontend/src/main.tsx**

```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

- [ ] **Step 6: Crear frontend/src/index.css**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg-base: #0f1117;
  --bg-panel: #0d1117;
  --bg-card: #1e2a3a;
  --bg-surface: #161b27;
  --border: #2d3748;
  --border-dim: #21262d;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-dim: #64748b;
  --text-dimmer: #374151;
  --accent-green: #4ade80;
  --accent-blue: #60a5fa;
  --accent-purple: #a78bfa;
  --accent-yellow: #fbbf24;
  --accent-red: #f87171;
  --font-mono: 'Courier New', 'Consolas', monospace;
}

body {
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
  overflow: hidden;
  height: 100vh;
}

.app {
  display: grid;
  grid-template-rows: auto 1fr;
  height: 100vh;
  overflow: hidden;
}

.split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  overflow: hidden;
  height: 100%;
}

/* Scrollbars */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
```

- [ ] **Step 7: Instalar dependencias del frontend**

```bash
cd frontend
npm install
cd ..
```

Expected: `node_modules/` creado, sin errores.

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffold — Vite + React + TypeScript + proxy config"
```

---

## Task 9: TypeScript types + useWebSocket hook

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/hooks/useWebSocket.ts`

- [ ] **Step 1: Crear frontend/src/types/index.ts**

```typescript
// frontend/src/types/index.ts

export interface Place {
  id: string
  name: string
  slug: string
  description: string
  shortDescription: string | null
  address: string
  city: string
  department: string
  country: string
  latitude: number | null
  longitude: number | null
  mainImage: string | null
  phone: string | null
  email: string | null
  website: string | null
  category: 'monuments' | 'nature' | 'viewpoints' | 'cultural'
}

export interface LogEntry {
  level: 'info' | 'warn' | 'error'
  message: string
  timestamp: string
}

export interface ScrapingStats {
  places_found: number
  cities_done: number
  cities_total: number
  current_city: string
  current_department: string
  errors: number
  status: 'idle' | 'running' | 'paused' | 'completed'
}

export type WsMessage =
  | { type: 'connected'; session_id: string }
  | { type: 'log'; level: LogEntry['level']; message: string; timestamp: string }
  | { type: 'place_found'; place: Place }
  | { type: 'progress'; cities_done: number; cities_total: number; places_found: number; current_city: string; current_department: string }
  | { type: 'city_completed'; city: string; places_count: number; duplicates_skipped: number }
  | { type: 'scrape_complete'; total_places: number; duration_seconds: number; errors: number }
  | { type: 'error'; message: string; city?: string }
```

- [ ] **Step 2: Crear frontend/src/hooks/useWebSocket.ts**

```typescript
// frontend/src/hooks/useWebSocket.ts
import { useEffect, useRef, useState, useCallback } from 'react'
import type { WsMessage } from '../types'

interface Options {
  onMessage: (msg: WsMessage) => void
  reconnectDelay?: number
}

export function useWebSocket(url: string, { onMessage, reconnectDelay = 3000 }: Options) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const onMessageRef = useRef(onMessage)
  const shouldReconnect = useRef(true)

  // Mantener la ref actualizada sin recrear el efecto
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  const connect = useCallback(() => {
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data) as WsMessage
        onMessageRef.current(msg)
      } catch {
        console.error('WS parse error', event.data)
      }
    }

    ws.onclose = () => {
      setConnected(false)
      if (shouldReconnect.current) {
        setTimeout(connect, reconnectDelay)
      }
    }

    ws.onerror = () => ws.close()
  }, [url, reconnectDelay])

  useEffect(() => {
    shouldReconnect.current = true
    connect()
    return () => {
      shouldReconnect.current = false
      wsRef.current?.close()
    }
  }, [connect])

  return { connected }
}
```

- [ ] **Step 3: Verificar que TypeScript compila sin errores**

```bash
cd frontend && npx tsc --noEmit && cd ..
```

Expected: Sin output (sin errores).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/ frontend/src/hooks/
git commit -m "feat: TypeScript types + useWebSocket hook with auto-reconnect"
```

---

## Task 10: StatsBar component

**Files:**
- Create: `frontend/src/components/StatsBar.tsx`

- [ ] **Step 1: Crear frontend/src/components/StatsBar.tsx**

```typescript
// frontend/src/components/StatsBar.tsx
import type { ScrapingStats } from '../types'

interface Props {
  stats: ScrapingStats
  connected: boolean
  onStart: () => void
  onPause: () => void
  onStop: () => void
  onExport: () => void
}

const STATUS_COLORS: Record<ScrapingStats['status'], string> = {
  idle: 'var(--text-dim)',
  running: 'var(--accent-green)',
  paused: 'var(--accent-yellow)',
  completed: 'var(--accent-blue)',
}

const STATUS_LABELS: Record<ScrapingStats['status'], string> = {
  idle: 'Inactivo',
  running: 'Scrapeando',
  paused: 'Pausado',
  completed: 'Completado',
}

export function StatsBar({ stats, connected, onStart, onPause, onStop, onExport }: Props) {
  const progress = stats.cities_total > 0
    ? Math.round((stats.cities_done / stats.cities_total) * 100)
    : 0

  const isRunning = stats.status === 'running'
  const statusColor = STATUS_COLORS[stats.status]

  return (
    <div style={{
      background: 'var(--bg-surface)',
      borderBottom: '1px solid var(--border)',
      padding: '10px 20px',
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
      flexWrap: 'wrap',
    }}>
      {/* Logo */}
      <div style={{ fontWeight: 700, fontSize: 15, display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap' }}>
        <span>🗺️</span> Colombia Tourist Scraper
      </div>

      {/* KPIs */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Chip value={stats.places_found} label="Lugares" color="var(--accent-green)" />
        <Chip value={`${stats.cities_done}/${stats.cities_total}`} label="Ciudades" color="var(--accent-blue)" />
        <Chip value={`${progress}%`} label="Progreso" color="var(--accent-purple)" />
        <Chip value={stats.errors} label="Errores" color={stats.errors > 0 ? 'var(--accent-red)' : 'var(--text-dim)'} />
      </div>

      {/* Barra de progreso */}
      <div style={{ flex: 1, minWidth: 150 }}>
        {stats.current_city && (
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>
            ⟳ {stats.current_city}, {stats.current_department}
          </div>
        )}
        <div style={{ height: 5, background: 'var(--bg-card)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            width: `${progress}%`,
            height: '100%',
            background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
            borderRadius: 3,
            transition: 'width 0.5s ease',
          }} />
        </div>
      </div>

      {/* Status badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: statusColor,
          animation: isRunning ? 'pulse 1.5s infinite' : 'none',
          display: 'inline-block',
        }} />
        <span style={{ color: statusColor }}>{STATUS_LABELS[stats.status]}</span>
        {!connected && <span style={{ color: 'var(--accent-red)', marginLeft: 6 }}>· WS desconectado</span>}
      </div>

      {/* Controles */}
      <div style={{ display: 'flex', gap: 8 }}>
        {!isRunning && (
          <Btn onClick={onStart} bg="#16a34a" label="▶ Iniciar" />
        )}
        {isRunning && (
          <>
            <Btn onClick={onPause} bg="#d97706" label="⏸ Pausar" />
            <Btn onClick={onStop} bg="#dc2626" label="⏹ Detener" />
          </>
        )}
        <Btn onClick={onExport} bg="#1e40af" label="⬇ Exportar JSON" />
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  )
}

function Chip({ value, label, color }: { value: string | number; label: string; color: string }) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: '5px 12px',
      textAlign: 'center',
      minWidth: 70,
    }}>
      <div style={{ fontSize: 18, fontWeight: 700, color, lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 2 }}>{label}</div>
    </div>
  )
}

function Btn({ onClick, bg, label }: { onClick: () => void; bg: string; label: string }) {
  return (
    <button onClick={onClick} style={{
      background: bg,
      color: 'white',
      border: 'none',
      borderRadius: 8,
      padding: '7px 14px',
      fontSize: 12,
      fontWeight: 600,
      cursor: 'pointer',
      whiteSpace: 'nowrap',
    }}>
      {label}
    </button>
  )
}
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd frontend && npx tsc --noEmit && cd ..
```

Expected: Sin errores.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/StatsBar.tsx
git commit -m "feat: StatsBar component — KPIs, progress bar, controls"
```

---

## Task 11: LogPanel component

**Files:**
- Create: `frontend/src/components/LogPanel.tsx`

- [ ] **Step 1: Crear frontend/src/components/LogPanel.tsx**

```typescript
// frontend/src/components/LogPanel.tsx
import { useEffect, useRef } from 'react'
import type { LogEntry } from '../types'

interface Props {
  logs: LogEntry[]
  currentCity?: string
}

const LEVEL_COLORS: Record<LogEntry['level'], string> = {
  info: 'var(--accent-green)',
  warn: 'var(--accent-yellow)',
  error: 'var(--accent-red)',
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('es-CO', {
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    })
  } catch {
    return '--:--:--'
  }
}

export function LogPanel({ logs, currentCity }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll al último log
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div style={{
      background: 'var(--bg-panel)',
      borderRight: '1px solid var(--border-dim)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '9px 16px',
        borderBottom: '1px solid var(--border-dim)',
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '1.5px',
        color: 'var(--text-dim)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span>📋 LOGS EN TIEMPO REAL</span>
        {currentCity && (
          <span style={{
            background: 'var(--bg-card)',
            color: 'var(--accent-blue)',
            borderRadius: 4,
            padding: '2px 8px',
            fontSize: 10,
            fontWeight: 600,
          }}>
            ⟳ {currentCity}
          </span>
        )}
      </div>

      {/* Logs */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '10px 14px',
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        lineHeight: 1.75,
      }}>
        {logs.length === 0 && (
          <div style={{ color: 'var(--text-dimmer)', fontStyle: 'italic' }}>
            Esperando inicio del scraping...
          </div>
        )}
        {logs.map((log, i) => (
          <div key={i} style={{ display: 'flex', gap: 10 }}>
            <span style={{ color: 'var(--text-dimmer)', minWidth: 60, flexShrink: 0 }}>
              {formatTime(log.timestamp)}
            </span>
            <span style={{ color: LEVEL_COLORS[log.level], wordBreak: 'break-word' }}>
              {log.message}
            </span>
          </div>
        ))}
        {/* Cursor parpadeante cuando hay actividad */}
        <div ref={bottomRef} style={{ height: 1 }} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd frontend && npx tsc --noEmit && cd ..
```

Expected: Sin errores.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LogPanel.tsx
git commit -m "feat: LogPanel component — colored real-time logs with auto-scroll"
```

---

## Task 12: PlaceCard + PlacesPanel components

**Files:**
- Create: `frontend/src/components/PlaceCard.tsx`
- Create: `frontend/src/components/PlacesPanel.tsx`

- [ ] **Step 1: Crear frontend/src/components/PlaceCard.tsx**

```typescript
// frontend/src/components/PlaceCard.tsx
import type { Place } from '../types'

interface Props {
  place: Place
}

const CATEGORY_CONFIG = {
  monuments: { emoji: '🏛️', label: 'Patrimonio',  bg: 'rgba(251,191,36,0.15)',  color: '#fbbf24', border: 'rgba(251,191,36,0.3)' },
  nature:    { emoji: '🌿', label: 'Naturaleza',   bg: 'rgba(74,222,128,0.15)',  color: '#4ade80', border: 'rgba(74,222,128,0.3)' },
  viewpoints:{ emoji: '🗺️', label: 'Mirador',      bg: 'rgba(96,165,250,0.15)',  color: '#60a5fa', border: 'rgba(96,165,250,0.3)' },
  cultural:  { emoji: '🏨', label: 'Cultural',     bg: 'rgba(167,139,250,0.15)', color: '#a78bfa', border: 'rgba(167,139,250,0.3)' },
}

export function PlaceCard({ place }: Props) {
  const config = CATEGORY_CONFIG[place.category] ?? CATEGORY_CONFIG.cultural

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: 12,
      display: 'flex',
      gap: 12,
      animation: 'slideIn 0.3s ease',
    }}>
      {/* Imagen o emoji */}
      <div style={{
        width: 48,
        height: 48,
        borderRadius: 8,
        flexShrink: 0,
        overflow: 'hidden',
        background: 'var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 22,
      }}>
        {place.mainImage
          ? <img src={place.mainImage} alt={place.name}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          : config.emoji
        }
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--text-primary)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {place.name}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
          {place.city} · {place.department}
        </div>

        {/* Tags */}
        <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
          <Tag bg={config.bg} color={config.color} border={config.border}>
            {config.emoji} {config.label}
          </Tag>
          {place.website && (
            <Tag bg="rgba(99,102,241,0.1)" color="#818cf8" border="rgba(99,102,241,0.3)">
              🔗 Web
            </Tag>
          )}
        </div>

        {/* Coordenadas */}
        {place.latitude && place.longitude && (
          <div style={{
            fontSize: 10,
            color: 'var(--text-dimmer)',
            fontFamily: 'var(--font-mono)',
            marginTop: 4,
          }}>
            {place.latitude.toFixed(4)}° N, {place.longitude.toFixed(4)}° W
          </div>
        )}
      </div>

      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(-6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}

function Tag({ bg, color, border, children }: {
  bg: string; color: string; border: string; children: React.ReactNode
}) {
  return (
    <span style={{
      fontSize: 10,
      padding: '2px 8px',
      borderRadius: 20,
      fontWeight: 500,
      background: bg,
      color,
      border: `1px solid ${border}`,
    }}>
      {children}
    </span>
  )
}
```

- [ ] **Step 2: Crear frontend/src/components/PlacesPanel.tsx**

```typescript
// frontend/src/components/PlacesPanel.tsx
import type { Place } from '../types'
import { PlaceCard } from './PlaceCard'

interface Props {
  places: Place[]
}

export function PlacesPanel({ places }: Props) {
  return (
    <div style={{
      background: '#111827',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '9px 16px',
        borderBottom: '1px solid var(--border-dim)',
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '1.5px',
        color: 'var(--text-dim)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span>🏛️ LUGARES ENCONTRADOS · {places.length}</span>
        <span style={{
          background: 'var(--bg-card)',
          color: 'var(--text-dim)',
          borderRadius: 4,
          padding: '2px 8px',
          fontSize: 10,
        }}>
          últimos primero
        </span>
      </div>

      {/* Cards */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}>
        {places.length === 0 && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: 'var(--text-dimmer)',
            fontStyle: 'italic',
            flexDirection: 'column',
            gap: 12,
          }}>
            <span style={{ fontSize: 40 }}>🇨🇴</span>
            <span>Los lugares aparecerán aquí en tiempo real</span>
          </div>
        )}
        {places.map((place) => (
          <PlaceCard key={place.id} place={place} />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verificar TypeScript**

```bash
cd frontend && npx tsc --noEmit && cd ..
```

Expected: Sin errores.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PlaceCard.tsx frontend/src/components/PlacesPanel.tsx
git commit -m "feat: PlaceCard + PlacesPanel components — animated cards with category tags"
```

---

## Task 13: App root — Split View

**Files:**
- Create: `frontend/src/App.tsx`

- [ ] **Step 1: Crear frontend/src/App.tsx**

```typescript
// frontend/src/App.tsx
import { useState, useCallback } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { StatsBar } from './components/StatsBar'
import { LogPanel } from './components/LogPanel'
import { PlacesPanel } from './components/PlacesPanel'
import type { Place, LogEntry, ScrapingStats, WsMessage } from './types'

const INITIAL_STATS: ScrapingStats = {
  places_found: 0,
  cities_done: 0,
  cities_total: 130,
  current_city: '',
  current_department: '',
  errors: 0,
  status: 'idle',
}

export default function App() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [places, setPlaces] = useState<Place[]>([])
  const [stats, setStats] = useState<ScrapingStats>(INITIAL_STATS)

  const handleMessage = useCallback((msg: WsMessage) => {
    switch (msg.type) {
      case 'log':
        setLogs(prev => [...prev.slice(-500), {
          level: msg.level,
          message: msg.message,
          timestamp: msg.timestamp,
        }])
        break
      case 'place_found':
        setPlaces(prev => [msg.place, ...prev])
        setStats(prev => ({ ...prev, places_found: prev.places_found + 1 }))
        break
      case 'progress':
        setStats(prev => ({
          ...prev,
          cities_done: msg.cities_done,
          cities_total: msg.cities_total,
          places_found: msg.places_found,
          current_city: msg.current_city,
          current_department: msg.current_department,
          status: 'running',
        }))
        break
      case 'city_completed':
        setLogs(prev => [...prev.slice(-500), {
          level: 'info',
          message: `✓ ${msg.city} → ${msg.places_count} lugares`,
          timestamp: new Date().toISOString(),
        }])
        break
      case 'scrape_complete':
        setStats(prev => ({ ...prev, status: 'completed' }))
        break
      case 'error':
        setStats(prev => ({ ...prev, errors: prev.errors + 1 }))
        break
    }
  }, [])

  const wsUrl = `ws://${window.location.host}/ws`
  const { connected } = useWebSocket(wsUrl, { onMessage: handleMessage })

  const handleStart = () =>
    fetch('/api/scrape/start', { method: 'POST' })
      .then(() => setStats(prev => ({ ...prev, status: 'running' })))

  const handlePause = () =>
    fetch('/api/scrape/pause', { method: 'POST' })
      .then(() => setStats(prev => ({ ...prev, status: 'paused' })))

  const handleStop = () =>
    fetch('/api/scrape/stop', { method: 'POST' })
      .then(() => setStats(prev => ({ ...prev, status: 'idle' })))

  const handleExport = () => window.open('/api/export/json', '_blank')

  return (
    <div className="app">
      <StatsBar
        stats={stats}
        connected={connected}
        onStart={handleStart}
        onPause={handlePause}
        onStop={handleStop}
        onExport={handleExport}
      />
      <div className="split">
        <LogPanel logs={logs} currentCity={stats.current_city || undefined} />
        <PlacesPanel places={places} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verificar TypeScript completo**

```bash
cd frontend && npx tsc --noEmit && cd ..
```

Expected: Sin errores.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: App root — Split View layout with real-time WebSocket state"
```

---

## Task 14: run.sh + README + smoke test

**Files:**
- Create: `run.sh`
- Create: `README.md`

- [ ] **Step 1: Crear run.sh**

```bash
#!/usr/bin/env bash
# run.sh — Arranca backend y frontend juntos
set -e

# Activar virtualenv si existe
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

echo "🐍 Iniciando backend en http://localhost:8000 ..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "⚛️  Iniciando frontend en http://localhost:5173 ..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Todo corriendo:"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:5173"
echo "   API docs: http://localhost:8000/docs"
echo ""
echo "Presiona Ctrl+C para detener ambos"

# Esperar y limpiar al salir
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Detenido.'" EXIT
wait $BACKEND_PID $FRONTEND_PID
```

```bash
chmod +x run.sh
```

- [ ] **Step 2: Crear README.md**

```markdown
# 🗺️ Colombia Tourist Places Scraper

Extrae información de lugares turísticos públicos de Google Maps para ~130 ciudades
colombianas y los muestra en un dashboard React en tiempo real vía WebSockets.

## Stack

- **Backend:** Python 3.11 + FastAPI + Playwright + SQLite
- **Frontend:** React 18 + Vite + TypeScript + WebSockets

## Instalación

```bash
# Python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Frontend
cd frontend && npm install && cd ..
```

## Uso

```bash
./run.sh
```

Abre http://localhost:5173 — haz clic en **▶ Iniciar** para comenzar el scraping.

## Exportar datos

- Clic en **⬇ Exportar JSON** en el dashboard, o
- `GET http://localhost:8000/api/export/json`

El archivo `output/places.json` contiene todos los lugares. Archivos individuales
por ciudad en `output/by_city/`.

## Estructura de datos

```json
{
  "id": "uuid",
  "name": "Plaza de Bolívar",
  "slug": "plaza-de-bolivar-bogota",
  "description": "...",
  "shortDescription": "...",
  "address": "Cl. 10 #7-51, Bogotá",
  "city": "Bogotá",
  "department": "Cundinamarca",
  "country": "Colombia",
  "latitude": 4.5981,
  "longitude": -74.0759,
  "mainImage": "https://...",
  "phone": null,
  "email": null,
  "website": null,
  "category": "monuments"
}
```

## Categorías

| Categoría | Tipo de lugares |
|-----------|----------------|
| `monuments` | Plazas, iglesias, sitios arqueológicos, edificios patrimoniales |
| `nature` | Parques naturales, cascadas, senderos ecoturismo |
| `viewpoints` | Miradores, malecones, playas, lagunas |
| `cultural` | Barrios típicos, mercados artesanales, zonas gastronómicas |

## Tests

```bash
pytest -v
```
```

- [ ] **Step 3: Correr todos los tests**

```bash
pytest -v
```

Expected: Todos los tests en verde. Mínimo `14 passed`.

- [ ] **Step 4: Smoke test del backend**

```bash
# Terminal 1
source .venv/bin/activate && uvicorn backend.main:app --port 8000

# Terminal 2 (verificar endpoints)
curl http://localhost:8000/api/scrape/status
# Expected: {"running":false,"paused":false,...,"places":0}

curl http://localhost:8000/docs
# Expected: respuesta HTML (Swagger UI)
```

- [ ] **Step 5: Smoke test del frontend**

```bash
cd frontend && npm run dev
# Abrir http://localhost:5173 en el navegador
# Expected: Dashboard con StatsBar, LogPanel vacío y PlacesPanel vacío
# El badge WS debe aparecer conectado (verde) cuando el backend está corriendo
```

- [ ] **Step 6: Commit final**

```bash
git add run.sh README.md
git commit -m "feat: run.sh + README — project complete and ready to scrape"
```

---

## Self-Review

**Cobertura del spec:**

| Sección | Tarea |
|---------|-------|
| Arquitectura FastAPI monolito | Tasks 6, 7 |
| Modelo Place + SQLite | Task 2 |
| city_progress (reanudación) | Task 2 |
| Lista de ciudades ~130 | Task 3 |
| Búsquedas por categoría | Task 3 |
| Playwright scraper + anti-detección | Task 7 |
| WebSocket ConnectionManager | Task 5 |
| REST endpoints (start/pause/stop/status/export/places) | Task 6 |
| WebSocket events (log/place_found/progress/city_completed/scrape_complete) | Tasks 5, 7 |
| Pausa al terminar ciudad actual | Task 6 (`state.paused` check post-ciudad) |
| JSON exporter (places.json + by_city/) | Task 4 |
| React Split View | Tasks 10-13 |
| StatsBar con KPIs + controles | Task 10 |
| LogPanel con colores + auto-scroll | Task 11 |
| PlaceCard + PlacesPanel animadas | Task 12 |
| useWebSocket con reconexión | Task 9 |
| Proxy Vite → FastAPI | Task 8 |
| run.sh + README | Task 14 |

**Consistencia de tipos:**
- `Place.to_dict()` retorna `mainImage`, `shortDescription` (camelCase) ✓ — usado en `json_exporter.py`, `routes.py`, y `PlaceCard.tsx`
- `WsMessage` en `types/index.ts` cubre todos los eventos emitidos en `playwright_scraper.py` ✓
- `ScrapeState.running` verificado en `_run_scrape` y en `scrape_all` ✓
