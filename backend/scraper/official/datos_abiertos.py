"""Inventarios turísticos y de patrimonio publicados por alcaldías y
gobernaciones en datos.gov.co (Portal de Datos Abiertos del Estado).

Cada dataset se declara en ``data/fuentes_oficiales.json`` con el mapeo de sus
columnas. Varios traen coordenadas oficiales, que se usan directamente.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from ..municipalities import Municipality, by_dane, find_by_name, find_mentioned
from .heritage import clean_description, normalize
from .http import OfficialHttp
from .models import SOURCE_DATOS_ABIERTOS, Candidate

logger = logging.getLogger(__name__)

SOURCES_FILE = Path(__file__).resolve().parent.parent / "data" / "fuentes_oficiales.json"
SOCRATA = "https://www.datos.gov.co"


def load_registry() -> dict:
    return json.loads(SOURCES_FILE.read_text(encoding="utf-8"))


# ── Coordenadas en los formatos que usan los datasets ───────────────────────

_DMS = re.compile(
    r"(\d{1,3})\s*[°º]\s*(\d{1,2})?\s*['′]?\s*(\d{1,2}(?:[.,]\d+)?)?\s*(?:\"|″|'')?\s*([NSEWO])",
    re.IGNORECASE,
)
_PAIR = re.compile(r"(-?\d{1,2}[.,]\d{3,})\s*[,;\s]\s*(-?\d{2,3}[.,]\d{3,})")


def _dms_to_decimal(deg: str, minutes: Optional[str], seconds: Optional[str], hemi: str) -> float:
    value = float(deg) + float(minutes or 0) / 60 + float((seconds or "0").replace(",", ".")) / 3600
    return -value if hemi.upper() in ("S", "W", "O") else value


def parse_coordinates(value: Any) -> tuple[Optional[float], Optional[float]]:
    """Admite: GeoJSON Point, ubicación Socrata {latitude, longitude},
    "4.27, -74.76", "9.228000  -75.818400" y grados/minutos/segundos
    ("5º26'14.20\"N 72º26'58.03\"W", "3°32′00″N 75°57′00″O")."""
    if value is None:
        return None, None
    if isinstance(value, dict):
        if value.get("type") == "Point" and value.get("coordinates"):
            lng, lat = value["coordinates"][:2]
            return _valid(float(lat), float(lng))
        if "latitude" in value and "longitude" in value:
            try:
                return _valid(float(value["latitude"]), float(value["longitude"]))
            except (TypeError, ValueError):
                return None, None
        return None, None
    text = str(value)
    dms = _DMS.findall(text)
    if len(dms) >= 2:
        coords = [_dms_to_decimal(*d) for d in dms[:2]]
        hemis = [d[3].upper() for d in dms[:2]]
        lat, lng = (coords if hemis[0] in "NS" else coords[::-1])
        return _valid(lat, lng)
    pair = _PAIR.search(text)
    if pair:
        a, b = (float(x.replace(",", ".")) for x in pair.groups())
        return _valid(a, b)
    return None, None


# Caja de Colombia continental + San Andrés y Providencia.
def _valid(lat: float, lng: float) -> tuple[Optional[float], Optional[float]]:
    if -4.5 <= lat <= 14.0 and -82.0 <= lng <= -66.0:
        return lat, lng
    return None, None


# ── Lectura de un dataset ───────────────────────────────────────────────────

def _field(row: dict, spec: dict, key: str) -> Any:
    col = spec.get("campos", {}).get(key)
    return row.get(col) if col else None


def _municipality_for(row: dict, spec: dict, name: str, description: str) -> Optional[Municipality]:
    if spec.get("dane"):
        return by_dane().get(spec["dane"])
    dpto = spec.get("departamento")
    code = _field(row, spec, "dane")
    if code:
        return by_dane().get(str(code).split(".")[0].zfill(5))
    muni_name = _field(row, spec, "municipio")
    if muni_name:
        return find_by_name(str(muni_name), dpto)
    if dpto:
        return find_mentioned(f"{name}. {description}", dpto)
    return None


def _type_allowed(row_type: str, spec: dict) -> bool:
    norm = normalize(row_type)
    allowed = [normalize(t) for t in spec.get("tipos_permitidos", [])]
    excluded = [normalize(t) for t in spec.get("tipos_excluidos", [])]
    if allowed and norm not in allowed:
        return False
    return norm not in excluded


async def dataset_candidates(http: OfficialHttp, spec: dict) -> list[tuple[Municipality, Candidate]]:
    dataset_id = spec["id"]
    rows = await http.get_json(f"{SOCRATA}/resource/{dataset_id}.json", params={"$limit": 5000})
    if not isinstance(rows, list):
        logger.info("Dataset %s no disponible", dataset_id)
        return []

    out: list[tuple[Municipality, Candidate]] = []
    for row in rows:
        name = str(_field(row, spec, "nombre") or "").strip()
        if not name:
            continue
        row_type = str(_field(row, spec, "tipo") or "")
        if row_type and not _type_allowed(row_type, spec):
            continue
        description = clean_description(str(_field(row, spec, "descripcion") or ""))
        municipality = _municipality_for(row, spec, name, description)
        if municipality is None:
            continue
        lat, lng = parse_coordinates(_field(row, spec, "coordenadas"))
        address = str(_field(row, spec, "direccion") or "").strip()
        if address and parse_coordinates(address)[0] is not None:
            address = ""  # la "dirección" eran coordenadas
        name_col = spec["campos"]["nombre"]
        evidence = (f"{SOCRATA}/resource/{dataset_id}.json?"
                    f"{quote(name_col)}={quote(name)}")
        out.append((municipality, Candidate(
            name=name,
            description=description,
            address=address if address.lower() not in ("n/a", "na", "sin informacion") else "",
            latitude=lat,
            longitude=lng,
            type_hint=row_type,
            ownership=str(_field(row, spec, "propiedad") or ""),
            heritage_source=bool(spec.get("inventario_patrimonio")),
            source_url=f"{SOCRATA}/d/{dataset_id}",
            source_entity=spec["entidad"],
            source_type=SOURCE_DATOS_ABIERTOS,
            evidence_url=evidence,
        )))
    return out


async def all_dataset_candidates(http: OfficialHttp) -> dict[str, list[Candidate]]:
    """Candidatos de todos los datasets registrados, agrupados por código DANE."""
    by_code: dict[str, list[Candidate]] = {}
    for spec in load_registry().get("datasets", []):
        try:
            pairs = await dataset_candidates(http, spec)
        except Exception as e:  # un dataset roto no debe tumbar la corrida
            logger.warning("Dataset %s falló: %s", spec.get("id"), e)
            continue
        for municipality, candidate in pairs:
            by_code.setdefault(municipality.dane, []).append(candidate)
    return by_code
