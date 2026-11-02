"""Extracción de sitios desde páginas HTML de portales oficiales.

Las páginas de "Sitios de interés"/"Sitios turísticos" de alcaldías y
gobernaciones siguen casi siempre el mismo patrón editorial:

    <strong>TEMPLO PARROQUIAL DE NUESTRA SEÑORA DEL ROSARIO</strong>
    <img src="...">
    <p>Fue construido en 1.604 ...</p>

Es decir: un título corto (h2–h5 o negrita en su propia línea), una imagen y
la descripción. Este módulo convierte la página en esos bloques; decidir si un
bloque es un sitio patrimonial le toca a ``heritage.evaluate``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from .heritage import normalize

_STRIP_TAGS = ("script", "style", "noscript", "nav", "header", "footer",
               "aside", "iframe", "svg", "button", "select")
_CHROME_HINT = re.compile(
    r"(^|[\s_-])(menu|nav|navbar|footer|header|breadcrumb|sidebar|cookie|"
    r"social|share|banner|topbar|search|buscador|pie)([\s_-]|$)", re.I,
)
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BOLD_TAGS = {"strong", "b"}
_BLOCK_TAGS = {"p", "div", "span", "td", "li", "font", "h1", "h2", "h3", "h4", "h5", "h6"}

# Enlaces que llevan a páginas de turismo/patrimonio dentro de un portal.
TOURISM_LINK = re.compile(
    r"turis|sitios?[ -_]de[ -_]interes|sitios?[ -_]turistic|atractiv|patrimonio|"
    r"lugares|que[ -_]hacer|conoce[ -_](el|nuestro|a)|mi[ -_]municipio|"
    r"nuestro[ -_]municipio|informacion[ -_]del[ -_]municipio|cultura",
)
_LINK_EXCLUDE = re.compile(
    r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|jpg|jpeg|png|gif|mp4|mp3)(\?|$)|"
    r"mailto:|tel:|javascript:|facebook|twitter|instagram|youtube|whatsapp|"
    r"login|contratacion|secop|transparencia|pqr|noticia|news|convocatoria|"
    r"decreto|resolucion|acuerdo|presupuesto|rendicion|tramite|empleo|"
    r"calendario|evento|directorio|galeria|audio|video|mapa-del-sitio",
    re.I,
)


@dataclass
class Block:
    title: str
    text: str
    image: Optional[str] = None
    link: Optional[str] = None


def _is_chrome(el: Tag) -> bool:
    attrs = " ".join([el.get("id") or "", " ".join(el.get("class") or []),
                      el.get("role") or ""])
    return bool(attrs and _CHROME_HINT.search(attrs))


def _clean_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()
    return soup


def _strip_chrome(root: Tag) -> None:
    """Quita menús, migas de pan, barras sociales… dentro del contenido. Solo
    elementos pequeños respecto al contenido: un contenedor general con una
    clase "header" no debe arrastrar la página entera."""
    total = len(_text_of(root)) or 1
    for el in root.find_all(True):
        if getattr(el, "decomposed", False) or el.parent is None:
            continue
        if _is_chrome(el) and len(_text_of(el)) < 0.3 * total:
            el.decompose()


def _main_root(soup: BeautifulSoup) -> Tag:
    for selector in ("main", "article", "[role=main]", "#DeltaPlaceHolderMain",
                     "#contentBox", ".ms-rtestate-field", "#content", ".content",
                     "#contenido", ".contenido"):
        found = soup.select(selector)
        if found:
            if selector == ".ms-rtestate-field" and len(found) > 1:
                # Plantilla SharePoint de MinTIC: un campo por sitio.
                return found[0].find_parent(["div", "td", "body"]) or soup.body or soup
            return found[0]
    return soup.body or soup


def _text_of(el: Tag) -> str:
    return " ".join(el.get_text(" ", strip=True).split())


def _is_heading(el: Tag) -> bool:
    if el.name in _HEADING_TAGS:
        return True
    if el.name in _BOLD_TAGS:
        text = _text_of(el)
        if not (3 <= len(text) <= 110):
            return False
        # Negrita "suelta": es todo el texto de su bloque contenedor.
        parent = el.find_parent(_BLOCK_TAGS - _BOLD_TAGS)
        return parent is not None and _text_of(parent) == text
    return False


def _resolve(base_url: str, src: Optional[str]) -> Optional[str]:
    if not src or src.startswith("data:"):
        return None
    url = urljoin(base_url, src.strip())
    return url if urlparse(url).scheme in ("http", "https") else None


def extract_blocks(html: str, base_url: str) -> list[Block]:
    """Divide el contenido principal en bloques título → texto/imagen."""
    soup = _clean_soup(html)
    root = _main_root(soup)
    _strip_chrome(root)

    blocks: list[Block] = []
    current: Optional[Block] = None
    parts: list[str] = []
    inside_heading: Optional[Tag] = None

    def close():
        if current is not None:
            current.text = " ".join(" ".join(parts).split())
            blocks.append(current)

    for node in root.descendants:
        if inside_heading is not None:
            if node is inside_heading or inside_heading in getattr(node, "parents", []):
                continue
            inside_heading = None
        if isinstance(node, Tag):
            if _is_heading(node):
                close()
                parts = []
                a = node.find("a", href=True) or (node.parent if node.parent and node.parent.name == "a" else None)
                link = _resolve(base_url, a.get("href")) if isinstance(a, Tag) and a.get("href") else None
                current = Block(title=_text_of(node), text="", link=link)
                inside_heading = node
            elif node.name == "img" and current is not None and current.image is None:
                src = node.get("src") or node.get("data-src")
                current.image = _resolve(base_url, src)
        elif isinstance(node, NavigableString) and current is not None:
            text = str(node).strip()
            if text:
                parts.append(text)
    close()
    return [b for b in blocks if b.title]


def page_meta(html: str, base_url: str) -> dict:
    """Título, descripción e imagen OpenGraph de una página de detalle."""
    soup = BeautifulSoup(html, "lxml")

    def meta(*names: str) -> Optional[str]:
        for n in names:
            el = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if el and el.get("content"):
                return el["content"].strip()
        return None

    title = meta("og:title") or (soup.title.get_text(strip=True) if soup.title else "")
    h1 = soup.find("h1")
    clean = _clean_soup(html)
    root = _main_root(clean)
    _strip_chrome(root)
    paragraphs = [_text_of(p) for p in root.find_all("p")]
    body = " ".join(p for p in paragraphs if len(p) > 40) or _text_of(root)
    return {
        "title": _text_of(h1) if h1 else title,
        "description": body or meta("og:description", "description") or "",
        "image": _resolve(base_url, meta("og:image")),
    }


def tourism_links(html: str, base_url: str) -> list[str]:
    """Enlaces del mismo portal cuyo texto o URL apunta a turismo/patrimonio."""
    soup = BeautifulSoup(html, "lxml")
    base_host = urlparse(base_url).netloc.lower()
    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        url = _resolve(base_url, href)
        if not url or _LINK_EXCLUDE.search(url):
            continue
        if urlparse(url).netloc.lower() != base_host:
            continue
        label = normalize(f"{a.get_text(' ', strip=True)} {a.get('title') or ''}")
        target = normalize(urlparse(url).path.replace("/", " "))
        if not (TOURISM_LINK.search(label) or TOURISM_LINK.search(target)):
            continue
        url = url.split("#")[0]
        if url in seen or url.rstrip("/") == base_url.rstrip("/"):
            continue
        seen.add(url)
        # Prioridad: los que hablan explícitamente de sitios/turismo primero.
        score = 0 if re.search(r"sitio|turis|atractiv|patrimon", label + " " + target) else 1
        found.append((score, url))
    return [u for _, u in sorted(found, key=lambda x: x[0])]


def dedupe_blocks(blocks: Iterable[Block]) -> list[Block]:
    out: dict[str, Block] = {}
    for b in blocks:
        key = normalize(b.title)
        prev = out.get(key)
        if prev is None or len(b.text) > len(prev.text):
            out[key] = b
    return list(out.values())
