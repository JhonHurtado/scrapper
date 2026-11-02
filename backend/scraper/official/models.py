from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Tipos de fuente aceptados (todas públicas y verificables).
SOURCE_ALCALDIA = "alcaldia"
SOURCE_GOBERNACION = "gobernacion"
SOURCE_OFICINA_TURISMO = "oficina_turismo"
SOURCE_DATOS_ABIERTOS = "datos_abiertos"

SOURCE_LABELS = {
    SOURCE_ALCALDIA: "Alcaldía",
    SOURCE_GOBERNACION: "Gobernación",
    SOURCE_OFICINA_TURISMO: "Oficina de turismo",
    SOURCE_DATOS_ABIERTOS: "Datos abiertos (datos.gov.co)",
}


@dataclass
class Candidate:
    """Un sitio tal como lo publica una fuente oficial, antes de verificarlo."""
    name: str
    source_url: str
    source_entity: str
    source_type: str
    description: str = ""
    image: Optional[str] = None
    address: str = ""
    phone: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Pistas que da la propia fuente
    type_hint: str = ""
    ownership: str = ""
    heritage_source: bool = False
    # URL de la API/dataset con el registro exacto (cuando existe)
    evidence_url: str = ""
    extra: dict = field(default_factory=dict)
