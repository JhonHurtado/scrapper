"""Cliente HTTP para fuentes oficiales.

* Solo deja consultar dominios oficiales (``*.gov.co`` y los que se declaren en
  ``data/fuentes_oficiales.json``): es la garantía de que todo lo que entra al
  catálogo es verificable en una página del Estado.
* Respeta robots.txt y espacia las peticiones a un mismo host.
* Si un portal responde 401/403/429 se registra y se sigue: no se intenta
  evadir ningún control de acceso.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx

from ...config import config

logger = logging.getLogger(__name__)

_SOURCES_FILE = Path(__file__).resolve().parent.parent / "data" / "fuentes_oficiales.json"


def _load_extra_domains() -> set[str]:
    try:
        data = json.loads(_SOURCES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {d.lower().lstrip(".") for d in data.get("dominios_oficiales_adicionales", [])}


EXTRA_OFFICIAL_DOMAINS = _load_extra_domains()


def is_official_url(url: str) -> bool:
    """True si la URL pertenece a una entidad pública colombiana."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if host.endswith(".gov.co") or host == "gov.co":
        return True
    return any(host == d or host.endswith("." + d) for d in EXTRA_OFFICIAL_DOMAINS)


class NotOfficialError(ValueError):
    pass


@dataclass
class Response:
    url: str
    status: int
    text: str
    content_type: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def json(self) -> Any:
        return json.loads(self.text)


class OfficialHttp:
    """Wrapper asíncrono con cortesía por host. Usar como context manager."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client
        self._own_client = client is None
        self._last_hit: dict[str, float] = {}
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._robots: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self.blocked_hosts: set[str] = set()

    async def __aenter__(self) -> "OfficialHttp":
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": config.http_user_agent,
                    "Accept-Language": "es-CO,es;q=0.9",
                },
                timeout=config.http_timeout,
                follow_redirects=True,
            )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._own_client and self._client is not None:
            await self._client.aclose()

    # ── cortesía ────────────────────────────────────────────────────────────
    async def _wait_turn(self, host: str) -> None:
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            elapsed = time.monotonic() - self._last_hit.get(host, 0.0)
            if elapsed < config.http_host_delay:
                await asyncio.sleep(config.http_host_delay - elapsed)
            self._last_hit[host] = time.monotonic()

    async def _allowed_by_robots(self, url: str) -> bool:
        if not config.respect_robots:
            return True
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            parser: Optional[urllib.robotparser.RobotFileParser] = None
            try:
                await self._wait_turn(parsed.netloc)
                r = await self._client.get(urljoin(origin, "/robots.txt"))
                ctype = r.headers.get("content-type", "")
                # Los portales SPA devuelven su index.html para cualquier ruta:
                # eso no es un robots.txt, así que no restringe nada.
                if r.status_code == 200 and "html" not in ctype:
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse(r.text.splitlines())
            except httpx.HTTPError:
                parser = None
            self._robots[origin] = parser
        parser = self._robots[origin]
        return parser is None or parser.can_fetch(config.http_user_agent, url)

    # ── peticiones ──────────────────────────────────────────────────────────
    async def get(self, url: str, params: Optional[dict] = None,
                  accept: str = "*/*") -> Optional[Response]:
        """GET a una fuente oficial. Devuelve None si no se pudo (red, robots,
        bloqueo); nunca lanza por errores de red."""
        if not is_official_url(url):
            raise NotOfficialError(url)
        host = urlparse(url).netloc
        if host in self.blocked_hosts:
            return None
        if not await self._allowed_by_robots(url):
            logger.info("robots.txt no permite %s", url)
            return None

        candidates = [url]
        # Muchos portales municipales solo funcionan en http o solo en https.
        if url.startswith("https://"):
            candidates.append("http://" + url[len("https://"):])
        elif url.startswith("http://"):
            candidates.append("https://" + url[len("http://"):])

        last_error: Optional[Exception] = None
        for candidate in candidates:
            for attempt in range(config.max_retries):
                await self._wait_turn(host)
                try:
                    r = await self._client.get(candidate, params=params,
                                               headers={"Accept": accept})
                except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                    last_error = e
                    break  # probar el otro esquema
                except httpx.HTTPError as e:
                    last_error = e
                    await asyncio.sleep(min(2 ** attempt, 8))
                    continue
                final = str(r.url)
                if not is_official_url(final):
                    logger.warning("Redirección fuera de dominio oficial: %s -> %s", url, final)
                    return None
                if r.status_code in (401, 403, 429):
                    logger.info("Acceso restringido (%s) en %s; se omite", r.status_code, host)
                    if r.status_code != 429:
                        self.blocked_hosts.add(host)
                    return Response(final, r.status_code, "", r.headers.get("content-type", ""))
                if r.status_code >= 500 and attempt < config.max_retries - 1:
                    await asyncio.sleep(min(2 ** attempt, 8))
                    continue
                return Response(final, r.status_code, r.text, r.headers.get("content-type", ""))
        if last_error:
            logger.info("No se pudo consultar %s: %s", url, last_error)
        return None

    async def get_json(self, url: str, params: Optional[dict] = None) -> Optional[Any]:
        r = await self.get(url, params=params, accept="application/json")
        if r is None or not r.ok:
            return None
        try:
            return r.json()
        except ValueError:
            return None
