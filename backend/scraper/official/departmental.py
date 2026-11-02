"""Portales departamentales: gobernaciones y oficinas/institutos de turismo.

Sus páginas de turismo listan sitios de varios municipios, así que cada ficha
se atribuye al municipio del departamento que mencione (primero en el título,
luego en la descripción). Si no menciona ninguno, se descarta: no se puede
verificar dónde está.
"""
from __future__ import annotations

import logging

from ..municipalities import (all_departments, all_municipalities, by_dane,
                              find_mentioned)
from .datos_abiertos import load_registry
from .http import OfficialHttp
from .models import SOURCE_GOBERNACION, Candidate
from .portal import portal_candidates

logger = logging.getLogger(__name__)


def _assign(candidates: list[Candidate], department_code: str,
            fixed_dane: str = "") -> dict[str, list[Candidate]]:
    out: dict[str, list[Candidate]] = {}
    for c in candidates:
        if fixed_dane:
            code = fixed_dane
        else:
            m = find_mentioned(c.name, department_code) or \
                find_mentioned(c.description, department_code)
            if m is None:
                continue
            code = m.dane
        out.setdefault(code, []).append(c)
    return out


def _merge(into: dict[str, list[Candidate]], more: dict[str, list[Candidate]]) -> None:
    for code, items in more.items():
        into.setdefault(code, []).extend(items)


async def departmental_candidates(http: OfficialHttp, log=None) -> dict[str, list[Candidate]]:
    """Candidatos de gobernaciones y de las páginas de turismo registradas,
    agrupados por código DANE del municipio."""
    alcaldia_urls = {(m.alcaldia_url or "").rstrip("/") for m in all_municipalities()}
    result: dict[str, list[Candidate]] = {}

    for dpto in all_departments():
        url = (dpto.gobernacion_url or "").rstrip("/")
        # Bogotá D.C. y San Andrés: la "gobernación" es el mismo portal de la
        # alcaldía, que ya se recorre municipio por municipio.
        if not url or url in alcaldia_urls:
            continue
        try:
            found = await portal_candidates(
                http, url, entity=f"Gobernación de {dpto.name}",
                source_type=SOURCE_GOBERNACION,
            )
        except Exception as e:
            logger.warning("Gobernación de %s falló: %s", dpto.name, e)
            continue
        assigned = _assign(found, dpto.code)
        _merge(result, assigned)
        if log:
            await log(f"  Gobernación de {dpto.name}: "
                      f"{sum(len(v) for v in assigned.values())} fichas con municipio")

    for page in load_registry().get("paginas_turismo", []):
        dane = page.get("dane", "")
        dpto_code = page.get("departamento") or (dane[:2] if dane else "")
        if dane and dane not in by_dane():
            continue
        try:
            found = await portal_candidates(
                http, page["url"], entity=page["entidad"],
                source_type=page.get("tipo", "oficina_turismo"),
                municipality=by_dane()[dane].name if dane else "",
            )
        except Exception as e:
            logger.warning("Página de turismo %s falló: %s", page.get("url"), e)
            continue
        _merge(result, _assign(found, dpto_code, fixed_dane=dane))
    return result
