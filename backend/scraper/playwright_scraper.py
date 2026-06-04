# backend/scraper/playwright_scraper.py
import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from playwright.async_api import async_playwright, BrowserContext, Page

from ..config import config
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


class ScrapingError(Exception):
    pass


async def _retry_async(coro, max_retries: int = 3, delay: float = 5.0):
    last_error = None
    for attempt in range(max_retries):
        try:
            return await coro()
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay *= 1.5
    raise last_error


async def scrape_all(manager: ConnectionManager, state=None):
    init_db()
    init_city_progress(CITIES)
    pending = get_pending_cities()

    await _log(manager, "info",
               f"Iniciando scraping: {len(pending)} ciudades pendientes")

    start_time = datetime.now(timezone.utc)
    total_errors = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.headless)
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": random.randint(1366, 1920), "height": 900},
            locale="es-CO",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for i, city in enumerate(pending):
            if state and not state.running:
                await _log(manager, "info", "Scraping detenido por el usuario")
                break

            if state and state.paused:
                await _log(manager, "info", "Scraping pausado, esperando...")
                while state and state.paused and state.running:
                    await asyncio.sleep(1)
                if not state or not state.running:
                    break

            city_name = city["name"]
            department = city["department"]

            if state:
                state.current_city = city_name
                state.cities_done = i
                state.cities_total = len(pending)

            await _log(manager, "info",
                       f"-> Ciudad [{i + 1}/{len(pending)}]: {city_name}, {department}")
            await manager.broadcast({
                "type": "progress",
                "citiesDone": i,
                "citiesTotal": len(pending),
                "placesFound": count_places(),
                "currentCity": city_name,
                "currentDepartment": department,
            })

            city_places = 0
            city_dupes = 0

            for item in build_queries_for_city(city_name):
                query = item["query"]
                category = item["category"]

                if state and not state.running:
                    break

                await _log(manager, "info", f'  Busqueda: "{query}"')

                places, errors = await _scrape_query_with_retry(
                    context, query, city_name, department, category, manager
                )
                total_errors += errors
                if state:
                    state.errors = total_errors

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

                delay = random.uniform(config.request_delay_min, config.request_delay_max)
                await asyncio.sleep(delay)

            mark_city_complete(city_name, department, city_places)
            await _log(manager, "info",
                       f"✓ {city_name} completada -> {city_places} lugares"
                       f" ({city_dupes} dupl. omitidos)")
            await manager.broadcast({
                "type": "city_completed",
                "city": city_name,
                "placesCount": city_places,
                "duplicatesSkipped": city_dupes,
            })

            await asyncio.sleep(random.uniform(3.0, 6.0))

        await browser.close()

    duration = int((datetime.now(timezone.utc) - start_time).total_seconds())
    total = count_places()
    await manager.broadcast({
        "type": "scrape_complete",
        "totalPlaces": total,
        "durationSeconds": duration,
        "errors": total_errors,
    })
    await _log(manager, "info",
               f"Scraping completado: {total} lugares en {duration}s")


async def _scrape_query_with_retry(
    context: BrowserContext,
    query: str,
    city: str,
    department: str,
    category: str,
    manager: ConnectionManager,
) -> Tuple[List[Place], int]:
    async def _scrape():
        return await _scrape_query(context, query, city, department, category, manager)

    try:
        return await _retry_async(
            _scrape,
            max_retries=config.max_retries,
            delay=config.retry_delay,
        )
    except Exception as e:
        logger.error(f"Query '{query}' failed after {config.max_retries} attempts: {e}")
        return [], 1


async def _scrape_query(
    context: BrowserContext,
    query: str,
    city: str,
    department: str,
    category: str,
    manager: ConnectionManager,
) -> Tuple[List[Place], int]:
    page = await context.new_page()
    places = []
    errors = 0

    try:
        url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        await page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
        await asyncio.sleep(2)

        if await page.locator("form#captcha-form").count() > 0:
            await _log(manager, "warn",
                       "reCAPTCHA detectado -- esperando 60s...")
            await asyncio.sleep(60)
            await page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(3)

        feed = page.locator('div[role="feed"]')
        if await feed.count() == 0:
            return places, errors

        for _ in range(config.scroll_attempts):
            await feed.evaluate("el => el.scrollTo(0, el.scrollHeight)")
            await asyncio.sleep(1.5)

        items = await page.locator(".Nv2PK").all()
        found_count = 0

        for item in items[:config.max_places_per_query]:
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
                           f"  Error extrayendo lugar: {str(e)[:80]}")
                continue

        if found_count:
            await _log(manager, "info", f"  ✦ {found_count} lugares encontrados")

    except Exception as e:
        errors += 1
        await _log(manager, "error",
                   f"  Error en busqueda '{query}': {str(e)[:100]}")
    finally:
        await page.close()

    return places, errors


async def _extract_place(
    page: Page, city: str, department: str, category: str
) -> Optional[Place]:
    try:
        name_locator = page.locator("h1").first
        if await name_locator.count() == 0:
            return None
        name = (await name_locator.text_content(timeout=5000) or "").strip()
        if not name:
            return None

        lat, lng = _extract_coords(page.url)

        address = ""
        addr = page.locator('button[data-item-id="address"]').first
        if await addr.count() > 0:
            address = (await addr.text_content() or "").strip()

        phone = None
        phone_el = page.locator('button[data-item-id="phone"]').first
        if await phone_el.count() > 0:
            phone = (await phone_el.text_content() or "").strip() or None

        website = None
        web_el = page.locator('a[data-item-id="authority"]').first
        if await web_el.count() > 0:
            website = await web_el.get_attribute("href")

        main_image = None
        img = page.locator('button[jsaction*="heroHeaderImage"] img').first
        if await img.count() > 0:
            main_image = await img.get_attribute("src")

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


def _extract_coords(url: str) -> Tuple[Optional[float], Optional[float]]:
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