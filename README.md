# 🇨🇴 Colombia Tourist Scraper

A full-stack web scraper that collects **tourist place data** from Google Maps for Colombian cities, with a real-time monitoring dashboard.

---

## Features

- **~130 Colombian cities** — 32 department capitals, intermediate cities, and Pueblos Patrimonio
- **4 categories** — Monuments, Nature, Viewpoints, Cultural
- **Real-time dashboard** — live logs + place cards via WebSocket
- **Resumable scraping** — tracks per-city progress in SQLite; restarts from where it left off
- **Anti-detection** — random User-Agent, viewport, `navigator.webdriver` override, CAPTCHA pause
- **JSON export** — flat `places.json` + per-city files in `output/by_city/`

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.9 + |
| Node.js | 18 + |
| npm | 9 + |

### One-command launch

```bash
./run.sh
```

`run.sh` will:

1. Create a Python virtual environment (`.venv`) and install deps if missing
2. Install Playwright's Chromium browser if missing
3. Run `npm install` in `frontend/` if missing
4. Start the FastAPI backend on **http://localhost:8000**
5. Start the Vite dev server on **http://localhost:5173** (opens browser)

Press **Ctrl+C** to stop both processes.

---

## Manual Setup

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Project Structure

```
.
├── backend/
│   ├── main.py                  # FastAPI app + WebSocket endpoint
│   ├── api/
│   │   ├── routes.py            # REST endpoints (start/pause/stop/export)
│   │   └── websocket.py         # ConnectionManager (broadcast)
│   ├── database/
│   │   ├── db.py                # SQLite connection + schema init
│   │   └── models.py            # Place dataclass + CRUD functions
│   ├── scraper/
│   │   ├── playwright_scraper.py  # Core Playwright scraping logic
│   │   ├── cities.py            # List of ~130 Colombian cities
│   │   └── queries.py           # Search queries per category
│   └── exporters/
│       └── json_exporter.py     # Export to JSON files
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Root: Split View layout
│   │   ├── components/
│   │   │   ├── StatsBar.tsx     # KPI bar + control buttons
│   │   │   ├── LogPanel.tsx     # Real-time log feed
│   │   │   ├── PlaceCard.tsx    # Place info card
│   │   │   └── PlacesPanel.tsx  # Scrollable list of cards
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts  # Auto-reconnect WS hook
│   │   └── types/index.ts       # TypeScript types
│   └── vite.config.ts           # Dev proxy → localhost:8000
├── tests/                       # pytest test suite (21 tests)
├── output/                      # Generated JSON export
├── data.db                      # SQLite database (auto-created)
├── requirements.txt
└── run.sh
```

---

## API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/scrape/start` | Start scraping |
| `POST` | `/api/scrape/pause` | Pause after current city |
| `POST` | `/api/scrape/resume` | Resume from pause |
| `POST` | `/api/scrape/stop` | Stop after current city |
| `GET`  | `/api/scrape/status` | Current scraping state |
| `GET`  | `/api/export/json` | Download `places.json` |
| `GET`  | `/api/places?page=1&page_size=50` | Paginated place list |

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

## Data Schema

Each place is exported with these fields (camelCase for Prisma compatibility):

```jsonc
{
  "id": "uuid-v4",
  "name": "Catedral de Sal de Zipaquirá",
  "slug": "catedral-de-sal-de-zipaquira-zipaquira",
  "description": "...",
  "shortDescription": "... (first 160 chars)",
  "address": "Calle 1, Zipaquirá",
  "city": "Zipaquirá",
  "department": "Cundinamarca",
  "country": "Colombia",
  "latitude": 5.0231,
  "longitude": -74.0035,
  "mainImage": "https://...",
  "phone": "+57 ...",
  "email": null,
  "website": "https://...",
  "category": "monuments"
}
```

---

## Running Tests

```bash
source .venv/bin/activate
pytest -v
```

Expected: **21 passed**

---

## Notes

- Scraping respects a **2–4 s delay** between queries and **3–6 s** between cities to reduce bot-detection risk
- If a **CAPTCHA** is detected, the scraper pauses for 60 s and retries
- Duplicate places (same slug) are silently skipped
- Progress is stored in `city_progress` table — if you restart `run.sh`, already-completed cities are skipped
- To start fresh: `rm data.db`
