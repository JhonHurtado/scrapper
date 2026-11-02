"""Regenera backend/scraper/data/municipios.json desde datos oficiales.

Fuentes (datos.gov.co, Portal de Datos Abiertos del Estado colombiano):
  * DIVIPOLA — Códigos de municipios (DANE), con coordenadas de la cabecera:
    https://www.datos.gov.co/resource/gdxc-w37w.json
  * Portales Territoriales — Sitios web de alcaldías y gobernaciones (MinTIC):
    https://www.datos.gov.co/resource/cnky-uvcg.json

Uso:
    python scripts/build_municipios.py                 # verifica dominios faltantes
    python scripts/build_municipios.py --sin-verificar # solo descarga

El JSON resultante va versionado en el repo para que el scraper funcione sin
depender de que datos.gov.co responda en cada ejecución.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / "scraper" / "data" / "municipios.json"

DIVIPOLA_URL = "https://www.datos.gov.co/resource/gdxc-w37w.json?$limit=5000"
PORTALES_URL = (
    "https://www.datos.gov.co/resource/cnky-uvcg.json?$limit=5000"
    "&$where=tipo_entidad in ('Alcaldía','Gobernación')"
)
UA = "CityScout-Scraper/2.0 (+https://github.com/jhonhurtado/scrapper)"

# Dominios oficiales de las gobernaciones (verificados: todos son *.gov.co).
GOBERNACIONES = {
    "05": "https://www.antioquia.gov.co",
    "08": "https://www.atlantico.gov.co",
    "11": "https://bogota.gov.co",
    "13": "https://www.bolivar.gov.co",
    "15": "https://www.boyaca.gov.co",
    "17": "https://www.caldas.gov.co",
    "18": "https://www.caqueta.gov.co",
    "19": "https://www.cauca.gov.co",
    "20": "https://www.cesar.gov.co",
    "23": "https://www.cordoba.gov.co",
    "25": "https://www.cundinamarca.gov.co",
    "27": "https://www.choco.gov.co",
    "41": "https://www.huila.gov.co",
    "44": "https://www.laguajira.gov.co",
    "47": "https://www.magdalena.gov.co",
    "50": "https://www.meta.gov.co",
    "52": "https://www.narino.gov.co",
    "54": "https://www.nortedesantander.gov.co",
    "63": "https://www.quindio.gov.co",
    "66": "https://www.risaralda.gov.co",
    "68": "https://santander.gov.co",
    "70": "https://www.sucre.gov.co",
    "73": "https://tolima.gov.co",
    "76": "https://www.valledelcauca.gov.co",
    "81": "https://www.arauca.gov.co",
    "85": "https://www.casanare.gov.co",
    "86": "https://putumayo.gov.co",
    "88": "https://www.sanandres.gov.co",
    "91": "https://www.amazonas.gov.co",
    "94": "https://www.guainia.gov.co",
    "95": "https://www.guaviare.gov.co",
    "97": "https://www.vaupes.gov.co",
    "99": "https://www.vichada.gov.co",
}

# Nombre de departamento tal como lo usa el backend (prisma/data/places.json).
DEPARTMENT_DISPLAY = {
    "BOGOTÁ, D.C.": "Cundinamarca",
    "ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA": "San Andrés y Providencia",
}

# Nombre común (el que usa el backend) para municipios cuyo nombre oficial DANE
# es más largo. Clave = código DANE.
COMMON_NAMES = {
    "11001": "Bogotá",
    "76001": "Cali",
    "13001": "Cartagena",
    "54001": "Cúcuta",
    "13468": "Mompox",
    "88001": "San Andrés",
    "52835": "Tumaco",
    "70820": "Tolú",
    "25843": "Ubaté",
    "23417": "Lorica",
    "05364": "Jardín",
}

# Alcaldías que no aparecen en el directorio de Portales Territoriales (las
# capitales tienen portal propio). Se aceptan solo si responden y el dominio
# final sigue siendo *.gov.co — ver _verify_url.
ALCALDIAS_EXTRA = {
    "11001": ["https://bogota.gov.co"],
    "05001": ["https://www.medellin.gov.co"],
    "76001": ["https://www.cali.gov.co"],
    "08001": ["https://www.barranquilla.gov.co"],
    "13001": ["https://www.cartagena.gov.co"],
    "68001": ["https://www.bucaramanga.gov.co"],
    "66001": ["https://www.pereira.gov.co"],
    "73001": ["https://www.ibague.gov.co"],
    "17001": ["https://manizales.gov.co"],
    "52001": ["https://www.pasto.gov.co"],
    "41001": ["https://www.alcaldianeiva.gov.co", "https://www.neiva.gov.co"],
    "50001": ["https://www.villavicencio.gov.co"],
    "63001": ["https://www.armenia.gov.co"],
    "20001": ["https://www.valledupar-cesar.gov.co", "https://www.valledupar.gov.co"],
    "23001": ["https://www.monteria.gov.co", "https://www.monteria-cordoba.gov.co"],
    "70001": ["https://www.sincelejo.gov.co", "https://www.sincelejo-sucre.gov.co"],
    "19001": ["https://www.popayan.gov.co"],
    "27001": ["https://www.quibdo-choco.gov.co", "https://www.quibdo.gov.co"],
    "44001": ["https://www.riohacha-laguajira.gov.co", "https://www.riohacha.gov.co"],
    "88001": ["https://www.sanandres.gov.co"],
    "76520": ["https://www.palmira.gov.co"],
    "76109": ["https://www.buenaventura.gov.co"],
    "05615": ["https://www.rionegro.gov.co"],
    "25754": ["https://www.alcaldiasoacha.gov.co", "https://www.soacha-cundinamarca.gov.co"],
    "66170": ["https://www.dosquebradas.gov.co"],
    "76834": ["https://www.tulua.gov.co"],
    "68276": ["https://www.floridablanca.gov.co"],
    "68081": ["https://www.barrancabermeja.gov.co"],
}

_LOWER = {"de", "del", "la", "las", "los", "el", "y", "e", "en"}


def title_es(text: str) -> str:
    words = text.strip().lower().split()
    out = []
    for i, w in enumerate(words):
        if i > 0 and w in _LOWER:
            out.append(w)
        else:
            out.append("-".join(p[:1].upper() + p[1:] for p in w.split("-")))
    return " ".join(out)


def _float(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def _repair_url(url: str) -> str:
    """El directorio de MinTIC trunca las URL a 50 caracteres
    ("…-cundinamarca.go"): se completa el sufijo .gov.co."""
    url = url.strip().rstrip("/")
    scheme, _, host = url.partition("://")
    host = host.split("/")[0]
    if not host.endswith(".gov.co") and re.search(r"\.g(o(v(\.(c)?)?)?)?$", host):
        host = re.sub(r"\.g[ov.c]*$", ".gov.co", host)
    return f"{scheme}://{host}"


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in t if ch.isalnum())


def _verify_url(c: httpx.Client, url: str) -> str | None:
    """Devuelve la URL base si el portal existe y sigue en un dominio *.gov.co.
    403 cuenta como existente (firewall del sitio): el scraper lo reportará
    al visitarlo, no intenta evadirlo."""
    try:
        r = c.get(url, follow_redirects=True, timeout=15)
    except httpx.HTTPError:
        return None
    host = r.url.host or ""
    if (r.status_code < 400 or r.status_code == 403) and host.endswith(".gov.co"):
        return f"{r.url.scheme}://{host}"
    return None


def _guess_alcaldia(c: httpx.Client, code: str, name: str, dpto: str) -> str | None:
    pattern = f"https://www.{_slug(name)}-{_slug(dpto)}.gov.co"
    for url in ALCALDIAS_EXTRA.get(code, []) + [pattern]:
        found = _verify_url(c, url)
        if found:
            return found
    return None


def build(guess: bool = True) -> dict:
    with httpx.Client(headers={"User-Agent": UA}, timeout=60) as c:
        divipola = c.get(DIVIPOLA_URL).raise_for_status().json()
        portales = c.get(PORTALES_URL).raise_for_status().json()

    alcaldias = {}
    for r in portales:
        if r.get("tipo_entidad") != "Alcaldía" or not r.get("url"):
            continue
        code = str(r["codigo_municipio"]).zfill(5)
        alcaldias.setdefault(code, _repair_url(r["url"]))

    departments: dict = {}
    municipios = []
    for r in sorted(divipola, key=lambda x: x["cod_mpio"]):
        dpto_code = r["cod_dpto"].zfill(2)
        dpto_name = DEPARTMENT_DISPLAY.get(r["dpto"], title_es(r["dpto"]))
        departments.setdefault(dpto_code, {
            "code": dpto_code,
            "name": dpto_name,
            "official_name": r["dpto"],
            "gobernacion_url": GOBERNACIONES.get(dpto_code),
        })
        code = r["cod_mpio"].zfill(5)
        official = r["nom_mpio"].replace(", D.C.", "")
        municipios.append({
            "dane": code,
            "name": COMMON_NAMES.get(code, title_es(official)),
            "official_name": title_es(official),
            "department": dpto_name,
            "department_code": dpto_code,
            "type": r.get("tipo_municipio") or "Municipio",
            "lat": _float(r.get("latitud")),
            "lng": _float(r.get("longitud")),
            "alcaldia_url": alcaldias.get(code),
        })

    if guess:
        with httpx.Client(headers={"User-Agent": UA}) as c:
            for m in municipios:
                if m["alcaldia_url"]:
                    continue
                if m["type"] != "Municipio" and m["dane"] not in ALCALDIAS_EXTRA:
                    continue
                dpto_official = departments[m["department_code"]]["official_name"]
                found = _guess_alcaldia(c, m["dane"], m["official_name"], dpto_official)
                if found:
                    m["alcaldia_url"] = found
                    print(f"  + {m['name']} ({m['department']}): {found}")

    return {
        "metadata": {
            "sources": [DIVIPOLA_URL, PORTALES_URL.split("&")[0]],
            "total_municipios": len(municipios),
            "con_portal_alcaldia": sum(1 for m in municipios if m["alcaldia_url"]),
        },
        "departments": sorted(departments.values(), key=lambda d: d["code"]),
        "municipios": municipios,
    }


def main() -> int:
    data = build(guess="--sin-verificar" not in sys.argv)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{OUT} · {data['metadata']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
