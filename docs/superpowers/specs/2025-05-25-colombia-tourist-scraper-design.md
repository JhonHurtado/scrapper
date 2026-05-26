# Colombia Tourist Places Scraper — Design Spec

**Fecha:** 2025-05-25  
**Estado:** Aprobado  
**Stack:** Python + FastAPI + Playwright + SQLite + React + Vite + TypeScript + WebSockets

---

## 1. Objetivo

Construir un sistema de Web Scraping que extraiga información de lugares turísticos públicos de las principales ciudades y Pueblos Patrimonio de Colombia desde Google Maps, la persista en SQLite, la exporte a JSON compatible con el modelo Prisma del proyecto, y proporcione una interfaz React en tiempo real para monitorear el proceso.

---

## 2. Alcance

- **~130 ciudades:** 32 capitales departamentales + ~40 ciudades intermedias + ~58 Pueblos Patrimonio de Colombia
- **4 categorías de lugares:**
  - `monuments` — iglesias, plazas históricas, edificios patrimoniales, sitios arqueológicos
  - `nature` — parques naturales, senderos, cascadas, reservas naturales
  - `viewpoints` — miradores, puntos panorámicos, malecones, playas, lagunas
  - `cultural` — barrios típicos, mercados artesanales, centros históricos, zonas gastronómicas
- **Estimado de resultados:** 1.500–2.500 lugares únicos
- **Tiempo estimado de scraping:** 4–8 horas en ejecución continua

---

## 3. Arquitectura — Enfoque A (Monolito FastAPI)

```
scrapper/
├── backend/
│   ├── main.py                  # FastAPI app + uvicorn entry point
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── playwright_scraper.py # Lógica principal de scraping
│   │   ├── cities.py             # Lista de 130 ciudades con departamento
│   │   └── queries.py            # Búsquedas por categoría
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py             # REST: /start, /pause, /stop, /export, /status
│   │   └── websocket.py          # WebSocket manager + broadcast
│   ├── database/
│   │   ├── __init__.py
│   │   ├── db.py                 # Conexión SQLite (sqlite3 nativo)
│   │   └── models.py             # Dataclass Place + queries CRUD
│   └── exporters/
│       └── json_exporter.py      # Genera places.json + by_city/*.json
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── StatsBar.tsx       # KPIs + controles Start/Pause/Stop/Export
│   │   │   ├── LogPanel.tsx       # Panel izquierdo: logs con colores
│   │   │   ├── PlacesPanel.tsx    # Panel derecho: tarjetas animadas
│   │   │   └── PlaceCard.tsx      # Tarjeta individual de lugar
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts    # Hook WebSocket con reconexión automática
│   │   └── types/
│   │       └── index.ts           # Tipos TypeScript (Place, LogEntry, ScrapingStatus)
│   ├── package.json
│   └── vite.config.ts
├── output/
│   ├── places.json               # Export completo
│   └── by_city/                  # bogota.json, medellin.json, etc.
├── data.db                       # SQLite
├── run.sh                        # Arranca backend + frontend juntos
├── requirements.txt
└── README.md
```

**Proceso de inicio:**
```bash
./run.sh
# → uvicorn backend.main:app --port 8000
# → cd frontend && npm run dev --port 5173
```

---

## 4. Modelo de Datos

### SQLite — tabla `places`

```sql
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
```

### SQLite — tabla `scrape_sessions`

```sql
CREATE TABLE IF NOT EXISTS scrape_sessions (
    id               TEXT PRIMARY KEY,
    started_at       TEXT NOT NULL,
    completed_at     TEXT,
    cities_processed INTEGER DEFAULT 0,
    total_places     INTEGER DEFAULT 0,
    status           TEXT DEFAULT 'running'  -- running | paused | completed | error
);
```

### SQLite — tabla `city_progress`

Permite reanudar el scraping desde donde se dejó sin repetir ciudades ya procesadas.

```sql
CREATE TABLE IF NOT EXISTS city_progress (
    city_slug        TEXT PRIMARY KEY,   -- "bogota", "medellin", etc.
    city_name        TEXT NOT NULL,
    department       TEXT NOT NULL,
    status           TEXT DEFAULT 'pending',  -- pending | completed | error
    places_found     INTEGER DEFAULT 0,
    completed_at     TEXT
);
```

### Python Dataclass

```python
@dataclass
class Place:
    id: str                      # UUID
    name: str
    slug: str                    # "plaza-de-bolivar-bogota"
    description: str
    short_description: str | None
    address: str
    city: str
    department: str
    country: str = "Colombia"
    latitude: float | None = None
    longitude: float | None = None
    main_image: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    category: str = ""           # monuments | nature | viewpoints | cultural
    scraped_at: str = ""
    source_url: str | None = None
```

---

## 5. Estrategia de Scraping

### Búsquedas por ciudad y categoría

```python
CATEGORY_QUERIES = {
    "monuments":  ["monumentos históricos en {city}", "iglesias patrimonio en {city}", "sitios arqueológicos en {city}"],
    "nature":     ["parques naturales en {city}", "cascadas cerca de {city}", "senderos ecoturismo {city}"],
    "viewpoints": ["miradores en {city}", "malecón de {city}", "playas cerca de {city}"],
    "cultural":   ["barrios típicos de {city}", "mercados artesanales en {city}", "turismo cultural {city}"],
}
```

### Flujo por ciudad

```
1. Navegar a maps.google.com
2. Buscar: "{query}"
3. Esperar resultados → scroll hasta cargar todos (máx 20 resultados por búsqueda)
4. Para cada resultado:
   a. Click en el item
   b. Esperar panel lateral
   c. Extraer: nombre, dirección, coords (de URL), teléfono, website, foto principal, descripción
   d. Generar slug único: slugify(name) + "-" + slugify(city)
   e. Verificar duplicado por slug en SQLite
   f. Guardar en SQLite
   g. Emitir evento WebSocket: place_found
5. Emitir evento WebSocket: city_completed
6. Esperar 3–6 segundos (jitter aleatorio, anti-bloqueo)
```

### Anti-detección

- User-agent rotación (lista de 10+ UAs reales de Chrome)
- Delays aleatorios entre requests (3–6s entre ciudades, 1–2s entre lugares)
- Viewport aleatorio (1280–1920px)
- Detección de reCAPTCHA → pausa automática 60s y reintento
- Máximo 3 reintentos por ciudad antes de marcar como `error` y continuar

---

## 6. API — Endpoints REST

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/scrape/start` | Inicia el scraping (asyncio background task) |
| `POST` | `/api/scrape/pause` | Pausa al terminar la ciudad actual (no interrumpe mid-scraping) |
| `POST` | `/api/scrape/stop` | Detiene el scraping completamente |
| `GET`  | `/api/scrape/status` | Estado actual (ciudad, progreso, lugares) |
| `GET`  | `/api/export/json` | Descarga `places.json` |
| `GET`  | `/api/places` | Lista paginada de lugares en SQLite |
| `WS`   | `/ws` | WebSocket para eventos en tiempo real |

---

## 7. Protocolo WebSocket

### Eventos servidor → cliente

```typescript
// Conexión establecida
{ type: "connected", session_id: string }

// Log de actividad
{ type: "log", level: "info" | "warn" | "error", message: string, timestamp: string }

// Nuevo lugar encontrado
{ type: "place_found", place: Place }

// Progreso general
{ type: "progress", cities_done: number, cities_total: number, places_found: number, current_city: string, current_department: string }

// Ciudad completada
{ type: "city_completed", city: string, places_count: number, duplicates_skipped: number }

// Scraping finalizado
{ type: "scrape_complete", total_places: number, duration_seconds: number, errors: number }

// Error recuperable
{ type: "error", message: string, city?: string }
```

### Comandos cliente → servidor

```typescript
{ type: "ping" }  // heartbeat
```

Los controles (start/pause/stop) se envían via REST, no por WebSocket.

---

## 8. Interfaz de Usuario

### Layout general

```
┌──────────────────────────────────────────────────────────┐
│ 🗺️ Colombia Tourist Scraper  [247] [23/130] [18%] [0err] │
│                               [▶ Start] [⏸ Pause] [⬇ JSON]│
├──────────────────────┬───────────────────────────────────┤
│  📋 LOGS EN TIEMPO   │  🏛️ LUGARES ENCONTRADOS · 247      │
│  REAL                │                                   │
│                      │  ┌─────────────────────────────┐  │
│  09:01 ▶ Iniciando   │  │ 🏔️ Nevado del Ruiz          │  │
│  09:01 ✓ SQLite OK   │  │    Manizales · Caldas        │  │
│  09:02 → Bogotá      │  │    🌿 Naturaleza  🗺️ Mirador  │  │
│  09:03 ✦ 12 lugares  │  └─────────────────────────────┘  │
│  09:04 → Medellín    │  ┌─────────────────────────────┐  │
│  09:24 ⟳ Manizales.. │  │ ⛪ Catedral de Manizales    │  │
│         ▌            │  │    Manizales · Caldas        │  │
│                      │  │    🏛️ Patrimonio              │  │
│                      │  └─────────────────────────────┘  │
└──────────────────────┴───────────────────────────────────┘
```

### Componentes React

| Componente | Responsabilidad |
|-----------|----------------|
| `StatsBar` | KPIs (lugares, ciudades, progreso, errores) + botones de control + barra de progreso |
| `LogPanel` | Lista de logs coloreados (verde/amarillo/rojo/azul) con scroll automático al último |
| `PlacesPanel` | Grid de `PlaceCard` con animación slide-in al aparecer, scroll independiente |
| `PlaceCard` | Emoji/imagen, nombre, ciudad·departamento, tags de categoría, coordenadas |
| `useWebSocket` | Hook que mantiene conexión WS, reconexión automática en 3s si se cae |

### Colores por categoría

| Categoría | Color | Emoji |
|-----------|-------|-------|
| `monuments` | Amarillo `#fbbf24` | 🏛️ |
| `nature` | Verde `#4ade80` | 🌿 |
| `viewpoints` | Azul `#60a5fa` | 🗺️ |
| `cultural` | Púrpura `#a78bfa` | 🏨 |

---

## 9. Formato de Exportación JSON

### `output/places.json`

```json
{
  "metadata": {
    "exported_at": "2025-05-25T10:00:00",
    "total_places": 1842,
    "cities_covered": 130,
    "categories": ["monuments", "nature", "viewpoints", "cultural"],
    "scraper_version": "1.0.0"
  },
  "places": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Plaza de Bolívar",
      "slug": "plaza-de-bolivar-bogota",
      "description": "La Plaza de Bolívar es la plaza principal de Bogotá...",
      "shortDescription": "Plaza principal de Bogotá, centro histórico y político del país.",
      "address": "Cl. 10 #7-51, Bogotá",
      "city": "Bogotá",
      "department": "Cundinamarca",
      "country": "Colombia",
      "latitude": 4.5981,
      "longitude": -74.0759,
      "mainImage": "https://lh5.googleusercontent.com/...",
      "phone": null,
      "email": null,
      "website": null,
      "category": "monuments"
    }
  ]
}
```

### `output/by_city/bogota.json`

Mismo formato, filtrado solo por la ciudad correspondiente.

---

## 10. Manejo de Errores y Resiliencia

- **Duplicados:** slug único en SQLite; si ya existe, se omite silenciosamente (log `dim`)
- **reCAPTCHA:** pausa automática 60s → reintento → si falla 3 veces, ciudad marcada como `error` y continúa
- **Timeout:** cada acción de Playwright tiene timeout de 15s; si falla, log de warning y continúa con el siguiente lugar
- **Reconexión WS:** el hook `useWebSocket` reconecta automáticamente tras 3s de desconexión
- **Reanudación:** la sesión guarda en SQLite qué ciudades fueron completadas; al reiniciar, salta las ya procesadas

---

## 11. Dependencias

### Python (`requirements.txt`)
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
playwright>=1.44.0
python-slugify>=8.0.4
websockets>=12.0
aiofiles>=23.2.1
```

### Frontend (`package.json`)
```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.4.0",
    "vite": "^5.3.0"
  }
}
```

`vite.config.ts` incluye proxy para desarrollo, evitando CORS:

```typescript
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/ws': { target: 'ws://localhost:8000', ws: true }
  }
}
```

---

## 12. Decisiones de Diseño

| Decisión | Alternativa considerada | Razón |
|----------|------------------------|-------|
| FastAPI monolito | Scraper desacoplado | Más simple de arrancar y mantener para este alcance |
| SQLite nativo | SQLAlchemy ORM | Sin dependencias extra; sqlite3 viene en stdlib de Python |
| Vite + React | Next.js | No se necesita SSR; Vite es más rápido para dev |
| WebSocket nativo FastAPI | Socket.io | Menos dependencias; FastAPI tiene soporte nativo |
| Playwright headless | Selenium | API más moderna y confiable para Google Maps |
