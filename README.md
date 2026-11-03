# 🇨🇴 Colombia Patrimonio Scraper

Scraper full-stack que recopila **solo sitios públicos de patrimonio cultural y
turístico** de los municipios de Colombia, tomados de **fuentes oficiales
verificables** (alcaldías, gobernaciones, oficinas de turismo y datos.gov.co),
con un dashboard de monitoreo en tiempo real. Su salida es el catálogo que carga
`backend-cityscout-2.0` (`prisma/data/places.json` → `npm run seed:places`).

---

## Cómo garantiza que la información sea oficial y verificable

1. **Solo fuentes del Estado.** El cliente HTTP (`backend/scraper/official/http.py`)
   rechaza cualquier URL que no sea `*.gov.co` (o un dominio declarado en
   `data/fuentes_oficiales.json`), y no sigue redirecciones que salgan de ellos.
   Respeta `robots.txt`, espacia las peticiones por host y, si un portal responde
   401/403/429, lo registra y sigue sin intentar evadirlo.
2. **Todos los municipios.** `data/municipios.json` sale de la DIVIPOLA del DANE
   (1.122 municipios y áreas no municipalizadas, con la coordenada de su
   cabecera) y del directorio de Portales Territoriales de MinTIC (URL oficial
   de cada alcaldía). Se regenera con `python scripts/build_municipios.py`.
3. **Fuentes por municipio:**
   - **Alcaldía.** La mayoría corre en la plataforma *Mi Colombia Digital*; se
     lee su API pública (`/api/v1/menufind`, `/api/v1/contents`): sección
     "Turismo"/"Sitios de interés" y búsqueda por tipo de sitio. Los portales
     antiguos (plantilla SharePoint de Gobierno en Línea) y otros CMS se leen
     como HTML ("Sitios de Interés", "Atractivos naturales", …).
   - **Gobernación / oficina de turismo.** Las fichas se atribuyen al municipio
     que mencionan; si no mencionan ninguno, se descartan.
   - **datos.gov.co.** Inventarios turísticos y de patrimonio publicados por
     alcaldías y gobernaciones (varios con coordenadas oficiales), declarados en
     `data/fuentes_oficiales.json` con el mapeo de columnas.
4. **Solo patrimonio público** (`official/heritage.py`): el nombre debe empezar
   por un tipo de sitio (Iglesia, Museo, Plaza, Puente, Parque Arqueológico,
   Cascada…); se descartan negocios (hotel, restaurante, finca, glamping, parque
   temático…), titulares de noticias, encabezados genéricos y lo que la fuente
   marque como propiedad privada. Los tipos ambiguos (una "casa", una
   "hacienda") exigen evidencia patrimonial en el texto oficial.
5. **Ubicación verificada** (`official/geocode.py`): coordenadas de la fuente
   oficial, o de OpenStreetMap (Nominatim) — o Google Maps como respaldo
   opcional — aceptadas solo si el nombre coincide en sus palabras distintivas,
   el punto cae dentro del radio del municipio (40 km de la cabecera; 150 km en
   Amazonía/Orinoquía) y no está en otro municipio.
6. **Trazabilidad.** Cada sitio guarda `sourceUrl` (página oficial),
   `sourceEntity`, `sourceType`, `evidenceUrl` (registro exacto en la API o el
   dataset), `daneCode`, `geoSource` y `verified`. Al backend solo se exportan
   los `verified` (el backend exige latitud/longitud).

## Características

- **1.122 municipios** (DIVIPOLA), empezando por capitales, ciudades
  intermedias y Pueblos Patrimonio; 1.073 con portal de alcaldía verificado.
- **20 categorías del backend** (`iglesias`, `museos`, `plazas`, `puentes`,
  `sitios_arqueologicos`, `cascadas`, `reservas_naturales`…). Se excluyen
  estadios, zoológicos y termales.
- **Dashboard en tiempo real** — logs y tarjetas por WebSocket, con la fuente
  oficial enlazada y el estado de verificación de cada sitio.
- **Reanudable** — el progreso se guarda por código DANE en SQLite.
- **Exportes** — `places.json` + `output/by_city/` y el catálogo para el backend.

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.9 + |
| Node.js | 18 + |
| npm | 9 + |

### One-command launch

**macOS / Linux:**

```bash
./run.sh
```

**Windows (PowerShell o cmd):**

```powershell
.\run.bat
# o directamente:
powershell -ExecutionPolicy Bypass -File run.ps1
```

Ambos scripts hacen lo mismo:

1. Crean el entorno virtual (`.venv`) si no existe e instalan las dependencias
   de Python cada vez que cambia `requirements.txt`
2. Buscan un navegador Chromium ya instalado (Brave, Chrome o Edge) para el
   respaldo de Google Maps — no descargan ningún navegador (ver abajo)
3. Run `npm install` in `frontend/` if missing
4. Start the FastAPI backend on **http://localhost:8000**
5. Start the Vite dev server on **http://localhost:5173** (opens browser)

Press **Ctrl+C** to stop both processes.

---

## Manual Setup

### Backend

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
# Windows (PowerShell): python -m venv .venv ; .venv\Scripts\Activate.ps1
# Windows (cmd):        python -m venv .venv && .venv\Scripts\activate.bat

pip install -r requirements.txt

uvicorn backend.main:app --reload
```

### Navegador (Brave, Chrome, Edge)

El scraping de fuentes oficiales no usa navegador: son peticiones HTTP a los
portales `*.gov.co`. Solo el respaldo opcional de ubicación en Google Maps abre
uno, y usa el que ya tengas instalado — en orden: **Brave**, Chrome, Edge,
Chromium. No hace falta `playwright install`.

```bash
python -m backend.scraper.official.browser      # muestra cuál se va a usar
SCRAPER_BROWSER=brave ./run.sh                  # forzar Brave
SCRAPER_BROWSER_PATH="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" ./run.sh
GEOCODER_GOOGLE_FALLBACK=false ./run.sh         # sin respaldo de Google Maps
```

> **Safari** no es posible: Playwright solo controla navegadores Chromium,
> Firefox y su propio WebKit, no la aplicación Safari. Si pides
> `SCRAPER_BROWSER=safari` se usa el primer navegador Chromium instalado.
> Si no tienes ninguno, se puede descargar el de Playwright con
> `python -m playwright install chromium`.

> **Windows**: el backend fija la política Proactor de asyncio y, si el servidor
> corre sobre un SelectorEventLoop, el scraper se ejecuta en un hilo con su
> propio loop — Playwright necesita soporte de subprocess que el selector no tiene.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Estructura

```
.
├── backend/
│   ├── main.py                      # FastAPI + WebSocket
│   ├── api/routes.py                # start/pause/stop/export/purge
│   ├── database/                    # SQLite: places, city_progress, geocode_cache
│   ├── scraper/
│   │   ├── official_scraper.py      # Bucle principal (también CLI)
│   │   ├── municipalities.py        # Catálogo DANE + portales de alcaldías
│   │   ├── cities.py                # Orden de prioridad (códigos DANE)
│   │   ├── data/
│   │   │   ├── municipios.json      # DIVIPOLA + URLs oficiales (generado)
│   │   │   └── fuentes_oficiales.json  # Datasets y páginas de turismo extra
│   │   └── official/
│   │       ├── http.py              # Cliente: solo *.gov.co, robots.txt, pausas
│   │       ├── mcd.py               # API de Mi Colombia Digital
│   │       ├── portal.py            # Portales HTML (SharePoint y otros)
│   │       ├── html_extract.py      # Página → bloques título/descripción/imagen
│   │       ├── departmental.py      # Gobernaciones y oficinas de turismo
│   │       ├── datos_abiertos.py    # Inventarios en datos.gov.co
│   │       ├── heritage.py          # ¿Es patrimonio público? ¿qué categoría?
│   │       └── geocode.py           # Ubicación verificada (OSM / Google)
│   └── exporters/
│       ├── json_exporter.py         # output/places.json + by_city/
│       └── prisma_exporter.py       # output/prisma/places.json (backend)
├── scripts/build_municipios.py      # Regenera data/municipios.json
├── frontend/                        # Dashboard (React + Vite)
└── tests/ , backend/tests/          # pytest (sin red: httpx.MockTransport)
```

### Ejecutar sin el dashboard

```bash
python -m backend.scraper.official_scraper                      # todo el país
python -m backend.scraper.official_scraper --solo 15407,68079   # Villa de Leyva y Barichara
python -m backend.scraper.official_scraper --sin-gobernaciones --sin-google
```

### Variables de entorno nuevas

| Variable | Por defecto | Uso |
|----------|-------------|-----|
| `ONLY_DANE_CODES` | (todos) | Municipios a recorrer, separados por coma |
| `INCLUDE_DEPARTMENTAL` | `true` | Recorrer portales de gobernaciones |
| `GEOCODER_GOOGLE_FALLBACK` | `true` | Google Maps si OpenStreetMap no ubica el sitio |
| `SCRAPER_BROWSER` | `auto` | `auto`, `brave`, `chrome`, `edge`, `chromium`, `playwright` o `none` |
| `SCRAPER_BROWSER_PATH` | — | Ruta exacta del ejecutable del navegador |
| `GEO_MAX_KM` / `GEO_MAX_KM_LARGE` | `40` / `150` | Radio máximo desde la cabecera municipal |
| `GEO_MIN_NAME_SIMILARITY` | `0.6` | Coincidencia mínima de nombre al geocodificar |
| `HTTP_HOST_DELAY_SECONDS` | `0.8` | Pausa entre peticiones a un mismo portal |
| `RESPECT_ROBOTS_TXT` | `true` | Respetar robots.txt |
| `HTTP_USER_AGENT` | `CityScout-Scraper/2.0 (+repo)` | Identificación ante portales y OSM |

---

## API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/scrape/start` | Iniciar |
| `POST` | `/api/scrape/pause` | Pausar después del municipio actual |
| `POST` | `/api/scrape/resume` | Reanudar |
| `POST` | `/api/scrape/stop` | Detener |
| `POST` | `/api/scrape/reset` | Volver a poner todos los municipios en pendiente |
| `GET`  | `/api/scrape/status` | Estado (incluye `verifiedCount` y `legacyCount`) |
| `GET`  | `/api/export/json` | `places.json` (todos los sitios oficiales) |
| `GET`  | `/api/export/backend` | `places.json` con el formato de `backend-cityscout-2.0` |
| `POST` | `/api/places/purge-legacy` | Borra lugares de la versión anterior (Google Maps sin fuente oficial) |
| `GET`  | `/api/places?page=1&per_page=50` | Lista paginada |

### WebSocket Events (`ws://localhost:8000/ws`)

All messages are JSON. The server sends:

| `type` | Payload |
|--------|---------|
| `connected` | `{ session_id }` |
| `log` | `{ level, message, timestamp }` |
| `progress` | `{ cities_done, cities_total, places_found, current_city, current_department }` |
| `place_found` | `{ place: Place }` |
| `city_completed` | `{ city, places_count, duplicates_skipped }` |
| `scrape_complete` | `{ total_places, duration_seconds, errors }` |

---

## Esquema de un sitio

```jsonc
{
  "name": "Casa Museo Antonio Nariño",
  "slug": "casa-museo-antonio-narino-villa-de-leyva",
  "description": "… texto oficial de la alcaldía …",
  "address": "Carrera 9 Nº 10-25",
  "city": "Villa de Leyva",
  "department": "Boyacá",
  "latitude": 5.6320868,
  "longitude": -73.5249697,
  "category": "museos",
  "sourceUrl": "https://www.villadeleyva-boyaca.gov.co/MiMunicipio/Paginas/Sitios-de-Interes.aspx",
  "sourceEntity": "Alcaldía de Villa de Leyva (Boyacá)",
  "sourceType": "alcaldia",          // alcaldia | gobernacion | oficina_turismo | datos_abiertos
  "evidenceUrl": "",                 // registro exacto en la API / dataset, si existe
  "daneCode": "15407",
  "geoSource": "openstreetmap",      // fuente_oficial | openstreetmap | google_maps
  "geoDistanceKm": 0.04,
  "verified": true
}
```

---

## Pruebas

```bash
source .venv/bin/activate
pytest -q
```

Las pruebas no usan red: las fuentes oficiales se simulan con `httpx.MockTransport`.

---

## Exportar al backend (CityScout 2.0)

```bash
.venv/bin/python -m backend.exporters.prisma_exporter        # macOS / Linux
.venv\Scripts\python -m backend.exporters.prisma_exporter    # Windows
cp output/prisma/places.json ../backend-cityscout-2.0/prisma/data/places.json
cd ../backend-cityscout-2.0 && npm run seed:places
```

`output/prisma/places.json` tiene el formato exacto que lee
`prisma/seed-places.ts` (`metadata.total_kept` + `categories.<categoria>[]`,
con las claves de categoría del seed del backend). Solo incluye sitios con
fuente oficial y ubicación verificada dentro de Colombia; `metadata.excluded_reasons`
dice cuántos quedaron fuera y por qué. Si un sitio no trae descripción, el seed
del backend genera la de respaldo ("<nombre>, en <ciudad> (<departamento>).").

## Notas

- Las bases de datos de la versión anterior (búsquedas en Google Maps) se
  migran solas: sus lugares quedan ocultos y fuera de los exportes; se borran con
  `POST /api/places/purge-legacy`. El progreso anterior por ciudad se descarta.
- Para empezar de cero: `rm data.db`.
- Para agregar un dataset o la página de una oficina de turismo, edita
  `backend/scraper/data/fuentes_oficiales.json` (debe ser de una entidad pública).
