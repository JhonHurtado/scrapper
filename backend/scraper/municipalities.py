"""Catálogo oficial de municipios (DANE · DIVIPOLA) con el portal de su alcaldía.

Los datos vienen de ``data/municipios.json``, generado por
``scripts/build_municipios.py`` a partir de datos.gov.co.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

from .official.heritage import normalize

DATA_FILE = Path(__file__).resolve().parent / "data" / "municipios.json"

# Amazonía y Orinoquía: municipios y áreas no municipalizadas enormes, donde un
# sitio puede estar a más de 100 km de la cabecera.
LARGE_DEPARTMENTS = {"18", "50", "81", "85", "86", "91", "94", "95", "97", "99"}


@dataclass(frozen=True)
class Municipality:
    dane: str
    name: str
    official_name: str
    department: str
    department_code: str
    type: str
    lat: Optional[float]
    lng: Optional[float]
    alcaldia_url: Optional[str]

    @property
    def is_large(self) -> bool:
        return self.department_code in LARGE_DEPARTMENTS or self.type != "Municipio"

    def as_progress(self) -> dict:
        return {"dane": self.dane, "name": self.name, "department": self.department}


@dataclass(frozen=True)
class Department:
    code: str
    name: str
    official_name: str
    gobernacion_url: Optional[str]


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def all_municipalities() -> tuple[Municipality, ...]:
    return tuple(Municipality(**m) for m in _data()["municipios"])


@lru_cache(maxsize=1)
def all_departments() -> tuple[Department, ...]:
    return tuple(Department(**d) for d in _data()["departments"])


def by_dane() -> dict[str, Municipality]:
    return {m.dane: m for m in all_municipalities()}


def department(code: str) -> Optional[Department]:
    return next((d for d in all_departments() if d.code == code), None)


def municipalities_of(department_code: str) -> list[Municipality]:
    return [m for m in all_municipalities() if m.department_code == department_code]


@lru_cache(maxsize=1)
def _duplicate_names() -> frozenset[str]:
    seen: dict[str, int] = {}
    for m in all_municipalities():
        seen[normalize(m.name)] = seen.get(normalize(m.name), 0) + 1
    return frozenset(n for n, c in seen.items() if c > 1)


def is_ambiguous_name(m: Municipality) -> bool:
    """True si hay otro municipio con el mismo nombre (p. ej. Villanueva)."""
    return normalize(m.name) in _duplicate_names()


def find_by_name(name: str, department_code: Optional[str] = None) -> Optional[Municipality]:
    """Busca por nombre común u oficial (sin tildes). Si hay homónimos y no se
    da el departamento, devuelve None: mejor no adivinar."""
    key = normalize(name)
    matches = [
        m for m in all_municipalities()
        if key in (normalize(m.name), normalize(m.official_name))
        and (department_code is None or m.department_code == department_code)
    ]
    return matches[0] if len(matches) == 1 else None


def ordered(priority_dane: Iterable[str]) -> list[Municipality]:
    """Primero los municipios prioritarios (capitales, Pueblos Patrimonio…), luego
    el resto en orden DANE."""
    index = by_dane()
    first = [index[c] for c in priority_dane if c in index]
    seen = {m.dane for m in first}
    return first + [m for m in all_municipalities() if m.dane not in seen]


@lru_cache(maxsize=64)
def _mention_patterns(department_code: str) -> list[tuple[re.Pattern, Municipality]]:
    patterns = []
    for m in municipalities_of(department_code):
        names = {normalize(m.name), normalize(m.official_name)}
        for n in names:
            if len(n) >= 4:
                patterns.append((re.compile(rf"\b{re.escape(n)}\b"), m))
    # Nombres largos primero: "San Juan de Arama" antes que "Arama".
    patterns.sort(key=lambda p: -len(p[0].pattern))
    return patterns


def find_mentioned(text: str, department_code: str) -> Optional[Municipality]:
    """Municipio del departamento que se menciona primero en el texto."""
    norm = normalize(text)
    best: Optional[tuple[int, Municipality]] = None
    for pattern, m in _mention_patterns(department_code):
        hit = pattern.search(norm)
        if hit and (best is None or hit.start() < best[0]):
            best = (hit.start(), m)
    return best[1] if best else None
