# backend/config.py
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).parent.parent / "data.db"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", Path(__file__).parent.parent / "output"))

PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
PLAYWRIGHT_TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "30000"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = float(os.getenv("RETRY_DELAY_SECONDS", "5.0"))

REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", "2.0"))
REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", "4.0"))

WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))

MAX_PLACES_PER_QUERY = int(os.getenv("MAX_PLACES_PER_QUERY", "20"))
SCROLL_ATTEMPTS = int(os.getenv("SCROLL_ATTEMPTS", "3"))


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
    max_places_per_query: int = MAX_PLACES_PER_QUERY
    scroll_attempts: int = SCROLL_ATTEMPTS

    @classmethod
    def from_env(cls) -> "Config":
        return cls()


config = Config.from_env()