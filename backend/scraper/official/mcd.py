"""Adaptador para la plataforma "Mi Colombia Digital" (MinTIC / Agencia Nacional
Digital), en la que corren la gran mayoría de portales de alcaldías.

El portal público (www.<municipio>-<departamento>.gov.co) es una SPA que lee una
API JSON pública en ``https://<sitio>.micolombiadigital.gov.co/api/v1``:

* ``/api/v1/config``                        → dominio de la API (authorityDomain)
* ``/api/v1/menufind?KeyWord=turismo``      → secciones de menú (con su tagID)
* ``/api/v1/contents?tags=<tagID>``         → fichas publicadas en esa sección
* ``/api/v1/contents?KeyWord=<texto>``      → búsqueda en todo el portal
* ``/api/v1/contents/<friendlyName>``       → ficha completa (cuerpo HTML)

Cada ficha se cita con su URL pública ``<portal>/<sección>/<friendlyName>`` y la
URL de la API como evidencia.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup

from ...config import config
from .heritage import clean_description, evaluate, extract_contact, normalize, strip_template
from .http import OfficialHttp, is_official_url
from .models import Candidate

logger = logging.getLogger(__name__)

# Secciones de menú que agrupan sitios turísticos/patrimoniales.
MENU_KEYWORDS = ("turismo", "turistico", "sitios", "atractivos", "patrimonio", "lugares")
TOURISM_TAG = re.compile(r"turis|sitios?|atractiv|patrimon|lugares|conoce|que hacer")
NOT_TOURISM_TAG = re.compile(r"secretar|salud|educaci|tramite|contrat|transparen|noticia")

# Búsquedas de texto en todo el portal (solo se aceptan resultados cuyo NOMBRE
# empieza por un tipo de sitio; los titulares de noticias quedan fuera).
SEARCH_KEYWORDS = (
    "sitios turisticos", "patrimonio", "iglesia", "capilla", "templo", "museo",
    "casa de la cultura", "parque", "plaza", "puente", "monumento", "mirador",
    "cascada", "laguna", "cerro", "parque arqueologico",
)
CONTENT_TYPES = {"Article", "Event", "Geolocation", "Information", "Info"}
# Secciones cuyas fichas no describen un sitio (noticias, galerías, videos…).
NOT_SITE_SECTION = re.compile(
    r"noticia|video|galeria|audio|evento|comunicado|boletin|prensa|convocatoria|"
    r"contrat|decreto|resolucion|informe|transparencia|rendicion|clasificado"
)
MAX_PAGES = 6       # páginas de 50 fichas por sección de turismo
SEARCH_PAGES = 2    # páginas de 50 resultados por búsqueda de texto


@dataclass
class McdSite:
    base_url: str          # portal público (www.<municipio>.gov.co)
    api: str               # https://<sitio>.micolombiadigital.gov.co
    entity: str            # "Alcaldía Municipal de Barichara, Santander"
    tag_slugs: dict = field(default_factory=dict)   # tagID -> friendlyName


async def detect(http: OfficialHttp, base_url: str) -> Optional[McdSite]:
    """Devuelve el sitio si el portal corre en Mi Colombia Digital."""
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    cfg = await http.get_json(origin + "/api/v1/config")
    if not isinstance(cfg, dict) or not cfg.get("authorityDomain"):
        return None
    api = str(cfg["authorityDomain"]).rstrip("/")
    if not is_official_url(api):
        return None
    entity = ((cfg.get("resources") or {}).get("Header.Title")
              or (cfg.get("resources") or {}).get("PageTitle.Home") or "")
    return McdSite(base_url=origin, api=api, entity=entity.strip())


async def _tourism_tags(http: OfficialHttp, site: McdSite) -> dict[int, str]:
    tags: dict[int, str] = {}
    for kw in MENU_KEYWORDS:
        found = await http.get_json(f"{site.api}/api/v1/menufind", params={"KeyWord": kw})
        for item in found or []:
            name = normalize(item.get("name") or "")
            tag_id = item.get("tagID")
            if tag_id and TOURISM_TAG.search(name) and not NOT_TOURISM_TAG.search(name):
                tags[int(tag_id)] = item.get("name") or ""
    for tag_id in tags:
        info = await http.get_json(f"{site.api}/api/v1/tags/{tag_id}")
        if isinstance(info, dict) and info.get("friendlyName"):
            site.tag_slugs[tag_id] = info["friendlyName"]
    return tags


async def _list_contents(http: OfficialHttp, site: McdSite, params: dict,
                         max_pages: int = MAX_PAGES) -> AsyncIterator[dict]:
    for page in range(max_pages):  # la API pagina desde 0
        data = await http.get_json(f"{site.api}/api/v1/contents",
                                   params={**params, "page": page, "pageSize": 50})
        if not isinstance(data, dict):
            return
        for item in data.get("results") or []:
            yield item
        if not (data.get("meta") or {}).get("hasNextPage"):
            return


def _body_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    return soup.get_text("\n", strip=True)


def public_url(site: McdSite, tag_slug: Optional[str], friendly: str) -> Optional[str]:
    """URL pública de la ficha: <portal>/<sección>/<ficha>."""
    if tag_slug:
        return f"{site.base_url}/{tag_slug}/{quote(friendly)}"
    return None


async def candidates(http: OfficialHttp, site: McdSite, municipality: str) -> list[Candidate]:
    """Fichas del portal que pasan el filtro de nombre; con su ficha completa."""
    tags = await _tourism_tags(http, site)
    pending: dict[str, tuple[dict, Optional[int]]] = {}

    # 1) Fichas de las secciones de turismo/patrimonio.
    for tag_id in tags:
        async for item in _list_contents(http, site, {"tags": tag_id}):
            pending.setdefault(item.get("friendlyName") or "", (item, tag_id))

    # 2) Búsqueda por tipo de sitio en todo el portal.
    for kw in SEARCH_KEYWORDS:
        async for item in _list_contents(http, site, {"KeyWord": kw}, max_pages=SEARCH_PAGES):
            if item.get("contentType") not in CONTENT_TYPES:
                continue
            pending.setdefault(item.get("friendlyName") or "", (item, None))
            if len(pending) > 400:
                break

    out: list[Candidate] = []
    details = 0
    for friendly, (item, tag_id) in pending.items():
        if not friendly:
            continue
        name = item.get("name") or ""
        summary = item.get("metaDescription") or ""
        # Filtro barato por nombre antes de pedir la ficha completa (la
        # evidencia patrimonial se exige después, con el texto completo).
        if not evaluate(name, summary, municipality=municipality,
                        heritage_source=True).accepted:
            continue
        if details >= config.max_details_per_municipality:
            break
        details += 1
        api_url = f"{site.api}/api/v1/contents/{quote(friendly)}"
        detail = await http.get_json(api_url)
        body = ""
        tag_slug = site.tag_slugs.get(tag_id) if tag_id else None
        image = item.get("defaultImage")
        if isinstance(detail, dict):
            body = _body_text(detail.get("body") or "")
            image = detail.get("defaultImage") or image
            for t in detail.get("tags") or []:
                if not tag_slug and t.get("friendlyName"):
                    tag_slug = t["friendlyName"]
        if tag_id is None and (not tag_slug or NOT_SITE_SECTION.search(tag_slug)):
            # Resultado de búsqueda publicado como noticia/galería/video: no
            # es la ficha oficial del sitio.
            continue
        text = body or summary
        contact = extract_contact(text)
        out.append(Candidate(
            name=name,
            description=clean_description(strip_template(text)),
            image=image if image and is_official_url(image) else None,
            address=contact.get("address", ""),
            phone=contact.get("phone"),
            email=contact.get("email"),
            source_url=public_url(site, tag_slug, friendly) or api_url,
            source_entity=site.entity,
            source_type="alcaldia",
            evidence_url=api_url,
        ))
    return out
