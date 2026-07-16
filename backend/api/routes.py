# backend/api/routes.py
import asyncio
import logging
import sys
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from ..config import config
from ..database.models import (
    count_places, get_all_places, get_places_by_city,
    get_city_progress, reset_city_progress,
)
from ..exporters.json_exporter import export_json
from .websocket import manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class ScrapeState:
    def __init__(self):
        self._running: bool = False
        self._paused: bool = False
        self._current_city: str = ""
        self._cities_done: int = 0
        self._cities_total: int = 0
        self._errors: int = 0
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._running

    @running.setter
    def running(self, value: bool):
        self._running = value

    @property
    def paused(self) -> bool:
        return self._paused

    @paused.setter
    def paused(self, value: bool):
        self._paused = value

    @property
    def current_city(self) -> str:
        return self._current_city

    @current_city.setter
    def current_city(self, value: str):
        self._current_city = value

    @property
    def cities_done(self) -> int:
        return self._cities_done

    @cities_done.setter
    def cities_done(self, value: int):
        self._cities_done = value

    @property
    def cities_total(self) -> int:
        return self._cities_total

    @cities_total.setter
    def cities_total(self, value: int):
        self._cities_total = value

    @property
    def errors(self) -> int:
        return self._errors

    @errors.setter
    def errors(self, value: int):
        self._errors = value

    def reset(self):
        self._running = False
        self._paused = False
        self._current_city = ""
        self._cities_done = 0
        self._cities_total = 0
        self._errors = 0


state = ScrapeState()


@router.post("/scrape/start")
async def start_scrape(background_tasks: BackgroundTasks):
    if state.running:
        raise HTTPException(status_code=409, detail="Scraping already in progress")

    state.running = True
    state.paused = False
    background_tasks.add_task(_run_scrape)
    return {"status": "started"}


def _loop_supports_playwright() -> bool:
    """Playwright lanza Chromium con subprocess; en Windows eso solo funciona
    sobre un ProactorEventLoop (uvicorn puede instalar un SelectorEventLoop)."""
    if sys.platform != "win32":
        return True
    return isinstance(asyncio.get_running_loop(), getattr(asyncio, "ProactorEventLoop", ()))


class LoopSafeManager:
    """Reenvía broadcasts del hilo del scraper al event loop del servidor."""

    def __init__(self, inner, server_loop: asyncio.AbstractEventLoop):
        self._inner = inner
        self._server_loop = server_loop

    async def broadcast(self, message: dict):
        asyncio.run_coroutine_threadsafe(self._inner.broadcast(message), self._server_loop)


def _scrape_in_proactor_thread(proxy: "LoopSafeManager"):
    """Corre el scraper en un loop Proactor propio (solo Windows)."""
    from ..scraper.playwright_scraper import scrape_all
    loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(scrape_all(proxy, state))
    finally:
        loop.close()


async def _run_scrape():
    from ..scraper.playwright_scraper import scrape_all
    try:
        if _loop_supports_playwright():
            await scrape_all(manager, state)
        else:
            proxy = LoopSafeManager(manager, asyncio.get_running_loop())
            await asyncio.to_thread(_scrape_in_proactor_thread, proxy)
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        await manager.broadcast({"type": "error", "message": str(e)})
    finally:
        state.running = False
        state.paused = False


@router.post("/scrape/pause")
async def pause_scrape():
    if not state.running:
        raise HTTPException(status_code=400, detail="No scraping in progress to pause")
    state.paused = True
    return {"status": "pausing"}


@router.post("/scrape/resume")
async def resume_scrape():
    if not state.running:
        raise HTTPException(status_code=400, detail="No scraping in progress to resume")
    state.paused = False
    return {"status": "resumed"}


@router.post("/scrape/stop")
async def stop_scrape():
    if not state.running:
        raise HTTPException(status_code=400, detail="No scraping in progress to stop")
    state.running = False
    state.paused = False
    return {"status": "stopped"}


@router.get("/scrape/status")
async def scrape_status():
    return {
        "running": state.running,
        "paused": state.paused,
        "currentCity": state.current_city,
        "citiesDone": state.cities_done,
        "citiesTotal": state.cities_total,
        "placesCount": count_places(),
        "errors": state.errors,
    }


@router.post("/scrape/reset")
async def reset_scrape():
    if state.running:
        raise HTTPException(status_code=409, detail="Cannot reset while scraping is running")
    reset_city_progress()
    return {"status": "reset"}


@router.get("/export/json")
async def export_places():
    try:
        path = export_json()
        return FileResponse(
            path=str(path),
            filename="places.json",
            media_type="application/json",
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/places")
async def list_places(
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=50, ge=1, le=200, description="Items per page"),
    city: Optional[str] = Query(default=None, description="Filter by city slug"),
):
    if city:
        places = get_places_by_city(city)
        total = len(places)
        start = (page - 1) * per_page
        end = start + per_page
        return {
            "total": total,
            "page": page,
            "perPage": per_page,
            "places": [p.to_dict() for p in places[start:end]],
        }

    total = count_places()
    offset = (page - 1) * per_page
    places = get_all_places()

    start = offset
    end = min(offset + per_page, total)

    return {
        "total": total,
        "page": page,
        "perPage": per_page,
        "places": [p.to_dict() for p in places[start:end]],
    }


@router.get("/cities")
async def list_cities():
    cities = get_city_progress()
    return {"cities": cities, "total": len(cities)}