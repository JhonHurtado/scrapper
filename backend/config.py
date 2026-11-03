# backend/config.py
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "si", "sí")


DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).parent.parent / "data.db"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", Path(__file__).parent.parent / "output"))

PLAYWRIGHT_HEADLESS = _bool("PLAYWRIGHT_HEADLESS", "true")
PLAYWRIGHT_TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "30000"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = float(os.getenv("RETRY_DELAY_SECONDS", "5.0"))

REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", "2.0"))
REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", "4.0"))

WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))

# ── Fuentes oficiales ────────────────────────────────────────────────────────
# Identificación honesta ante los portales del Estado y ante OpenStreetMap
# (su política de uso exige un User-Agent que identifique la aplicación).
HTTP_USER_AGENT = os.getenv(
    "HTTP_USER_AGENT",
    "CityScout-Scraper/2.0 (+https://github.com/jhonhurtado/scrapper)",
)
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "25"))
# Pausa mínima entre dos peticiones al MISMO host.
HTTP_HOST_DELAY_SECONDS = float(os.getenv("HTTP_HOST_DELAY_SECONDS", "0.8"))
RESPECT_ROBOTS_TXT = _bool("RESPECT_ROBOTS_TXT", "true")
# Páginas de turismo que se leen como máximo por portal (alcaldía/gobernación).
MAX_PAGES_PER_PORTAL = int(os.getenv("MAX_PAGES_PER_PORTAL", "8"))
# Fichas de detalle que se abren como máximo por municipio.
MAX_DETAILS_PER_MUNICIPALITY = int(os.getenv("MAX_DETAILS_PER_MUNICIPALITY", "60"))

# ── Geolocalización y verificación ───────────────────────────────────────────
# Distancia máxima (km) entre el sitio y la cabecera municipal (DANE).
GEO_MAX_KM = float(os.getenv("GEO_MAX_KM", "40"))
# Municipios de Amazonía/Orinoquía y áreas no municipalizadas son enormes.
GEO_MAX_KM_LARGE = float(os.getenv("GEO_MAX_KM_LARGE", "150"))
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
# Política de Nominatim: máximo 1 petición por segundo.
NOMINATIM_DELAY_SECONDS = float(os.getenv("NOMINATIM_DELAY_SECONDS", "1.1"))
# Si OpenStreetMap no ubica el sitio, intentar con Google Maps (Playwright).
GEOCODER_GOOGLE_FALLBACK = _bool("GEOCODER_GOOGLE_FALLBACK", "true")
# Navegador para ese respaldo: auto | brave | chrome | edge | chromium |
# playwright | none. "auto" usa el primero instalado (Brave primero), así no
# hace falta descargar el Chromium de Playwright. SCRAPER_BROWSER_PATH fija la ruta.
BROWSER = os.getenv("SCRAPER_BROWSER", "auto")
BROWSER_PATH = os.getenv("SCRAPER_BROWSER_PATH", "")
# Similitud mínima (0-1) entre el nombre oficial y el que devuelve el geocoder.
GEO_MIN_NAME_SIMILARITY = float(os.getenv("GEO_MIN_NAME_SIMILARITY", "0.6"))

# Recorrer también los portales de las gobernaciones (sitios de varios municipios).
INCLUDE_DEPARTMENTAL = _bool("INCLUDE_DEPARTMENTAL", "true")

# Limitar la ejecución a ciertos municipios (códigos DANE separados por coma).
ONLY_DANE_CODES = [c.strip() for c in os.getenv("ONLY_DANE_CODES", "").split(",") if c.strip()]


@dataclass
class Config:
    db_path: Path = DB_PATH
    output_dir: Path = OUTPUT_DIR
    headless: bool = PLAYWRIGHT_HEADLESS
    timeout_ms: int = PLAYWRIGHT_TIMEOUT_MS
    max_retries: int = MAX_RETRIES
    retry_delay: float = RETRY_DELAY_SECONDS
    request_delay_min: float = REQUEST_DELAY_MIN
    request_delay_max: float = REQUEST_DELAY_MAX
    ws_heartbeat: int = WS_HEARTBEAT_INTERVAL
    http_user_agent: str = HTTP_USER_AGENT
    http_timeout: float = HTTP_TIMEOUT_SECONDS
    http_host_delay: float = HTTP_HOST_DELAY_SECONDS
    respect_robots: bool = RESPECT_ROBOTS_TXT
    max_pages_per_portal: int = MAX_PAGES_PER_PORTAL
    max_details_per_municipality: int = MAX_DETAILS_PER_MUNICIPALITY
    geo_max_km: float = GEO_MAX_KM
    geo_max_km_large: float = GEO_MAX_KM_LARGE
    nominatim_url: str = NOMINATIM_URL
    nominatim_delay: float = NOMINATIM_DELAY_SECONDS
    geocoder_google_fallback: bool = GEOCODER_GOOGLE_FALLBACK
    browser: str = BROWSER
    browser_path: str = BROWSER_PATH
    geo_min_name_similarity: float = GEO_MIN_NAME_SIMILARITY
    include_departmental: bool = INCLUDE_DEPARTMENTAL
    only_dane_codes: tuple = tuple(ONLY_DANE_CODES)

    @classmethod
    def from_env(cls) -> "Config":
        return cls()


config = Config.from_env()
