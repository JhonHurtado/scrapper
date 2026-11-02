"""Lectura de un portal oficial (alcaldía, gobernación u oficina de turismo).

* Si el portal corre en Mi Colombia Digital → API JSON (``mcd.py``).
* Si no → HTML: se buscan en la portada los enlaces a turismo/patrimonio, se
  prueban las rutas estándar de la plantilla territorial de MinTIC
  (SharePoint) y cada página se divide en bloques título→descripción.
"""
from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

from ...config import config
from . import mcd
from .heritage import clean_description, evaluate, extract_contact, strip_template
from .html_extract import Block, dedupe_blocks, extract_blocks, page_meta, tourism_links
from .http import OfficialHttp, is_official_url
from .models import Candidate

logger = logging.getLogger(__name__)

# Rutas de la plantilla "Sitios Territoriales" (SharePoint) de Gobierno en Línea.
SHAREPOINT_PATHS = (
    "/MiMunicipio/Paginas/Sitios-de-Interes.aspx",
    "/MiMunicipio/Paginas/Sitios-Turisticos.aspx",
    "/MiMunicipio/Paginas/Atractivos-Turisticos.aspx",
    "/Paginas/Atractivos-Naturales.aspx",
    "/MiMunicipio/Paginas/Patrimonio.aspx",
    "/MiMunicipio/Paginas/cultura.aspx",
)

# Fichas de detalle que se siguen como máximo desde una página índice.
MAX_FOLLOW_LINKS = 25


def _looks_like_mcd_shell(html: str) -> bool:
    return "<title>Territoriales</title>" in html or "micolombiadigital" in html


async def _html_candidates(http: OfficialHttp, base_url: str, home_html: str,
                           municipality: str, include_self: bool = False
                           ) -> list[tuple[str, Block]]:
    pages = tourism_links(home_html, base_url)
    if include_self:
        # Se pidió una página concreta (p. ej. la de turismo de una
        # gobernación): también se leen sus propios bloques.
        pages.insert(0, base_url)
    if "/Paginas/" in home_html or "SharePoint" in home_html:
        pages += [urljoin(base_url, p) for p in SHAREPOINT_PATHS]
    seen: set[str] = set()
    queue = [p for p in pages if not (p in seen or seen.add(p))]

    found: list[tuple[str, Block]] = []
    visited = 0
    while queue and visited < config.max_pages_per_portal:
        url = queue.pop(0)
        visited += 1
        r = await http.get(url, accept="text/html")
        if r is None or not r.ok or "html" not in r.content_type:
            continue
        blocks = extract_blocks(r.text, r.url)
        found.extend((r.url, b) for b in blocks)
        # Un nivel más: "Turismo" suele enlazar a "Sitios turísticos".
        for link in tourism_links(r.text, r.url):
            if link not in seen:
                seen.add(link)
                queue.append(link)

    # Bloques que son solo un enlace a la ficha del sitio: se abre la ficha.
    followed = 0
    enriched: list[tuple[str, Block]] = []
    for page_url, block in found:
        if (block.link and len(block.text) < 60 and followed < MAX_FOLLOW_LINKS
                and is_official_url(block.link)
                and evaluate(block.title, "patrimonio", municipality=municipality).accepted):
            followed += 1
            r = await http.get(block.link, accept="text/html")
            if r is not None and r.ok and "html" in r.content_type:
                meta = page_meta(r.text, r.url)
                block = Block(title=block.title, text=meta["description"],
                              image=block.image or meta["image"], link=r.url)
                page_url = r.url
        enriched.append((page_url, block))
    return enriched


async def portal_candidates(
    http: OfficialHttp,
    base_url: str,
    *,
    entity: str,
    source_type: str,
    municipality: str = "",
) -> list[Candidate]:
    """Candidatos publicados por un portal oficial. ``municipality`` vacío
    significa portal departamental (el municipio se asigna después)."""
    if not base_url or not is_official_url(base_url):
        return []

    site = await mcd.detect(http, base_url)
    if site is not None:
        found = await mcd.candidates(http, site, municipality)
        for c in found:
            c.source_type = source_type
            c.source_entity = entity or c.source_entity
        return found

    r = await http.get(base_url, accept="text/html")
    if r is None or not r.ok:
        return []
    if _looks_like_mcd_shell(r.text):
        return []  # SPA de MCD sin API accesible: no hay contenido legible

    out: list[Candidate] = []
    for page_url, block in dedupe_blocks_with_url(
            await _html_candidates(http, r.url, r.text, municipality,
                                   include_self=urlparse(base_url).path not in ("", "/"))):
        text = block.text
        contact = extract_contact(text)
        out.append(Candidate(
            name=block.title,
            description=clean_description(strip_template(text)),
            image=block.image if block.image and is_official_url(block.image) else None,
            address=contact.get("address", ""),
            phone=contact.get("phone"),
            email=contact.get("email"),
            source_url=page_url,
            source_entity=entity,
            source_type=source_type,
        ))
    return out


def dedupe_blocks_with_url(items: list[tuple[str, Block]]) -> list[tuple[str, Block]]:
    by_block = {id(b): url for url, b in items}
    return [(by_block.get(id(b), ""), b) for b in dedupe_blocks(b for _, b in items)]


async def municipality_portal(http: OfficialHttp, municipality, entity: Optional[str] = None
                              ) -> list[Candidate]:
    """Atajo: portal de la alcaldía de un ``Municipality``."""
    return await portal_candidates(
        http, municipality.alcaldia_url or "",
        entity=entity or f"Alcaldía de {municipality.name} ({municipality.department})",
        source_type="alcaldia",
        municipality=municipality.name,
    )
