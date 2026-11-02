"""Decide si un candidato es un sitio PÚBLICO de patrimonio cultural/turístico
y en qué categoría del backend (prisma/seed.ts → CATEGORIES) cae.

Criterio deliberadamente estricto — se prefiere perder un sitio a publicar
algo que no lo es:

1. El nombre debe EMPEZAR por un sustantivo de tipo de sitio ("Iglesia…",
   "Museo…", "Parque…", "Puente…"). Así se descartan titulares de noticias
   ("Autorizan intervención de la capilla…"), encabezados genéricos
   ("Sitios de interés", "Cómo llegar") y frases sueltas.
2. El nombre no puede delatar un negocio privado (hotel, restaurante,
   finca, glamping, parque temático…).
3. Tipos ambiguos (una "casa", una "hacienda", un "edificio") solo pasan si la
   fuente aporta evidencia patrimonial: la propia fuente es un inventario de
   patrimonio, o el texto oficial habla de patrimonio, monumento nacional,
   arquitectura colonial/republicana, siglos, etc.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

# Categorías del backend (slug con guion bajo, como las claves de
# prisma/data/places.json) → nombre para mostrar.
BACKEND_CATEGORIES = {
    "barrios_y_zonas_urbanas": "Barrios y Zonas Urbanas",
    "cascadas": "Cascadas",
    "cementerios": "Cementerios",
    "centros_culturales": "Centros Culturales",
    "cerros_y_montanas": "Cerros y Montañas",
    "estadios_y_coliseos": "Estadios y Coliseos",
    "iglesias": "Iglesias",
    "lagos_y_lagunas": "Lagos y Lagunas",
    "mercados": "Mercados",
    "miradores": "Miradores",
    "monumentos": "Monumentos",
    "museos": "Museos",
    "naturaleza": "Naturaleza",
    "parques": "Parques",
    "playas_y_malecones": "Playas y Malecones",
    "plazas": "Plazas",
    "puentes": "Puentes",
    "reservas_naturales": "Reservas Naturales",
    "rios_y_balnearios": "Ríos y Balnearios",
    "sitios_arqueologicos": "Sitios Arqueológicos",
    "sitios_culturales": "Sitios Culturales",
    "termales": "Termales",
    "zoologicos_y_acuarios": "Zoológicos y Acuarios",
}

# Categorías que NO son patrimonio público aunque existan en el backend:
# estadios, zoológicos y termales (casi siempre balnearios privados).
EXCLUDED_CATEGORIES = {"estadios_y_coliseos", "zoologicos_y_acuarios", "termales"}

# (categoría, frases) — la frase debe ser el COMIENZO del nombre normalizado.
# Gana la frase más larga, así "parque arqueologico" vence a "parque".
_HEAD_PHRASES: list[tuple[str, tuple[str, ...]]] = [
    ("iglesias", (
        "iglesia", "catedral", "concatedral", "basilica", "capilla", "templo",
        "parroquia", "santuario", "ermita", "convento", "monasterio",
        "claustro", "recoleta",
    )),
    ("museos", ("museo", "casa museo", "casa-museo", "pinacoteca", "planetario")),
    ("centros_culturales", (
        "casa de la cultura", "casa de cultura", "centro cultural",
        "centro de memoria", "teatro", "biblioteca", "concha acustica",
        "archivo historico", "auditorio", "escuela taller",
    )),
    ("plazas", ("plaza", "plazoleta", "plazuela", "plaza principal", "plaza de bolivar")),
    ("mercados", ("plaza de mercado", "mercado publico", "mercado municipal", "mercado")),
    ("parques", (
        "parque", "parque principal", "parque central", "parque municipal",
        "alameda", "jardin botanico", "paseo", "bulevar", "boulevard",
    )),
    ("puentes", ("puente", "viaducto")),
    ("monumentos", (
        "monumento", "estatua", "busto", "obelisco", "fuerte", "fortaleza",
        "castillo", "baluarte", "muralla", "murallas", "bateria", "torre del reloj",
        "torre", "arco", "hito", "cruz", "cristo", "cristo rey", "mural",
        "escultura", "efigie",
    )),
    ("sitios_arqueologicos", (
        "parque arqueologico", "sitio arqueologico", "zona arqueologica",
        "petroglifo", "petroglifos", "pictografia", "pictografias", "pictograma",
        "arte rupestre", "piedra pintada", "piedras pintadas",
        "tumba", "tumbas", "hipogeo", "hipogeos", "estatuaria",
        "observatorio solar", "camino precolombino", "ciudad perdida",
    )),
    ("cementerios", ("cementerio", "mausoleo", "panteon")),
    ("sitios_culturales", (
        "casa de", "casa del", "casa natal", "casa consistorial", "casa colonial",
        "casona", "palacio", "edificio", "estacion", "estacion del ferrocarril",
        "hacienda", "molino", "camino real", "camino de", "antigua carcel",
        "carcel", "aduana", "trapiche", "colegio", "seminario", "claustro de",
        "alcaldia", "gobernacion", "hospital", "academia", "casa cural",
        "cabildo", "real fabrica", "fabrica", "faro", "plaza de toros", "casa",
    )),
    ("barrios_y_zonas_urbanas", (
        "centro historico", "barrio", "sector historico", "calle", "callejon",
        "pueblito", "conjunto urbano",
    )),
    ("miradores", ("mirador", "balcon", "balcones", "alto del mirador")),
    ("cascadas", ("cascada", "cascadas", "salto", "catarata", "cataratas", "chorro", "chorrera")),
    ("lagos_y_lagunas", ("laguna", "lagunas", "lago", "embalse", "represa", "cienaga", "humedal")),
    ("rios_y_balnearios", (
        "rio", "quebrada", "balneario", "charco", "pozo", "pozos", "playon",
        "rapidos", "estrecho",
    )),
    ("cerros_y_montanas", (
        "cerro", "cerros", "montana", "nevado", "volcan", "cuchilla", "pena",
        "penon", "alto de", "alto del", "serrania", "pico", "sierra", "loma",
        "piedra", "piedra del penol", "formacion rocosa",
    )),
    ("reservas_naturales", (
        "parque nacional natural", "parque nacional", "parque natural",
        "parque natural regional", "santuario de fauna", "santuario de flora",
        "reserva", "reserva natural", "area protegida", "paramo",
        "area natural unica", "santuario de fauna y flora",
        "distrito de manejo integrado", "via parque",
    )),
    ("naturaleza", (
        "cueva", "cuevas", "caverna", "gruta", "sendero", "bosque", "jardin",
        "canon", "desierto", "valle", "isla", "islote", "manglar", "parque ecologico",
        "arbol", "ceiba", "saman",
    )),
    ("termales", ("termales", "aguas termales", "termal")),
    ("playas_y_malecones", ("playa", "playas", "malecon", "muelle", "bahia", "ensenada")),
]

# Frases cuyo tipo es ambiguo (puede ser una vivienda privada o un negocio):
# requieren evidencia patrimonial.
_AMBIGUOUS = {
    "casa de", "casa del", "casona", "casa colonial", "edificio", "hacienda",
    "molino", "colegio", "hospital", "academia", "fabrica", "trapiche",
    "calle", "callejon", "barrio", "conjunto urbano", "torre", "arco",
    "cruz", "mural", "paseo", "arbol", "ceiba", "saman", "loma", "estacion",
    "pueblito", "mercado", "alcaldia", "gobernacion", "cabildo", "carcel",
    "plaza de toros", "piedra", "casa cural", "casa",
}

# Palabras iniciales que no cuentan para el sustantivo de cabeza.
_LEADING = (
    "el", "la", "los", "las", "antigua", "antiguo", "gran", "viejo", "vieja",
    "nuevo", "nueva", "historica", "historico", "imponente", "majestuoso",
    "majestuosa", "hermosa", "hermoso", "tradicional", "famoso", "famosa",
)

# Negocios o lugares privados: si el nombre contiene esto, fuera.
_BUSINESS = re.compile(
    r"\b(hotel(es)?|hostal|hostel|hospedaje|alojamiento|posada|caba[nñ]as?|glamping|"
    r"camping|finca|restaurante|asadero|cafeter[ií]a|caf[eé]|bar|discoteca|estadero|"
    r"fonda|piscinas?|club|condominio|centro comercial|tienda|almac[eé]n|"
    r"supermercado|droguer[ií]a|agencia|operador|tours?|travel|parque tem[aá]tico|"
    r"parque acu[aá]tico|parque de diversiones|spa|resort|ecohotel|motel|"
    r"inmobiliaria|parqueadero|panader[ií]a|artesan[ií]as|boutique|apartamentos?|"
    r"apartahotel|lavadero|gimnasio|gym|cooperativa|empresa|s\.?a\.?s\.?|ltda|"
    r"trivago|aviatur|booking|airbnb|tripadvisor)\b",
    re.IGNORECASE,
)

# Encabezados de página que nunca son un sitio.
_NOT_A_SITE = re.compile(
    r"^(sitios? (de interes|turisticos?)|atractivos? turisticos?|turismo|"
    r"galeria( de (imagenes|fotos|videos))?|contacto|direccion|horarios?|"
    r"como llegar|recomendaciones|informacion|historia|resena historica|"
    r"ubicacion|simbolos|escudo|bandera|himno|mapa|noticias|eventos?|"
    r"inicio|leer mas|ver mas|descargar|fuente|cruz roja|estacion de (policia|servicio|bomberos))\b",
)

# Evidencia patrimonial en el texto oficial.
_HERITAGE_EVIDENCE = re.compile(
    r"patrimonio|monumento nacional|bien(es)? de interes cultural|\bbic\b|"
    r"declarad[oa]|colonial|republican[oa]|historic[oa]|siglo|"
    r"construid[oa] (en|a|hacia|entre)|fundad[oa]|arquitectura|museo|"
    r"antigu[oa]|patrimonial|tradicion|ancestral|precolombin[oa]|"
    r"arqueologic[oa]|indigena|conservaci[oó]n",
)

# Señales de propiedad privada en campos estructurados (datos abiertos).
_PRIVATE_OWNERSHIP = re.compile(r"privad|particular", re.IGNORECASE)


def normalize(text: str) -> str:
    """minúsculas, sin tildes, sin signos, espacios simples."""
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9ñ\s]", " ", t.lower())
    return " ".join(t.split())


def clean_name(text: str) -> str:
    """Nombre presentable: sin espacios raros, sin viñetas ni dos puntos finales,
    y en formato título si venía TODO EN MAYÚSCULAS."""
    t = re.sub(r"[\u200b\u00a0\s]+", " ", text or "").strip()
    t = re.sub(r"^[\-–•·*\d.)\s]+", "", t)       # viñetas / numeración
    t = re.sub(r"[\s:–\-]+$", "", t)              # dos puntos / guion final
    t = t.strip("\"'“”«» ")
    if t.isupper() and len(t) > 3:
        t = _title_es(t)
    return t


_TITLE_LOWER = {"de", "del", "la", "las", "los", "el", "y", "e", "en", "a", "al", "o"}


def _title_es(text: str) -> str:
    words = text.lower().split()
    return " ".join(
        w if (i > 0 and w in _TITLE_LOWER) else w[:1].upper() + w[1:]
        for i, w in enumerate(words)
    )


@dataclass
class Classification:
    category: str
    head: str
    needs_evidence: bool


def _strip_leading(norm: str) -> str:
    words = norm.split()
    while words and words[0] in _LEADING:
        words = words[1:]
    return " ".join(words)


_HEADS_CACHE: list[tuple[str, str]] = []


def _heads() -> list[tuple[str, str]]:
    if not _HEADS_CACHE:
        _HEADS_CACHE.extend(
            (category, normalize(phrase))
            for category, phrases in _HEAD_PHRASES for phrase in phrases
        )
    return _HEADS_CACHE


def classify_name(name: str) -> Optional[Classification]:
    """Categoría por el sustantivo con que empieza el nombre; None si no empieza
    por un tipo de sitio reconocible."""
    norm = _strip_leading(normalize(name))
    if not norm:
        return None
    best: Optional[tuple[str, str]] = None
    for category, p in _heads():
        if norm == p or norm.startswith(p + " "):
            if best is None or len(p) > len(best[1]):
                best = (category, p)
    if best is None:
        return None
    category, head = best
    return Classification(category=category, head=head, needs_evidence=head in _AMBIGUOUS)


@dataclass
class Verdict:
    accepted: bool
    category: Optional[str] = None
    reason: str = ""


def evaluate(
    name: str,
    text: str = "",
    *,
    type_hint: str = "",
    ownership: str = "",
    heritage_source: bool = False,
    municipality: str = "",
) -> Verdict:
    """Veredicto completo para un candidato.

    name            nombre tal como lo publica la fuente oficial
    text            descripción oficial (se usa como evidencia patrimonial)
    type_hint       tipo declarado por la fuente (columna de un dataset)
    ownership       propiedad declarada por la fuente ("Pública"/"Privada")
    heritage_source True si la fuente es un inventario de patrimonio
    municipality    municipio al que se atribuye (descarta "Barichara Monumento
                    Nacional" y similares: hablan del pueblo, no de un sitio)
    """
    clean = clean_name(name)
    norm = normalize(clean)
    if len(norm) < 4 or len(clean) > 110 or len(norm.split()) > 14:
        return Verdict(False, reason="nombre con forma inválida")
    if len(_strip_leading(norm).split()) < 2:
        return Verdict(False, reason="nombre genérico (una sola palabra)")
    muni = normalize(municipality)
    if muni and (norm == muni or norm.startswith(muni + " ")):
        return Verdict(False, reason="habla del municipio, no de un sitio")
    if _NOT_A_SITE.match(norm):
        return Verdict(False, reason="encabezado genérico")
    if _BUSINESS.search(clean) or _BUSINESS.search(norm):
        return Verdict(False, reason="negocio privado")
    if ownership and _PRIVATE_OWNERSHIP.search(ownership):
        return Verdict(False, reason="propiedad privada según la fuente")

    cls = classify_name(clean)
    if cls is None and type_hint:
        # Fuentes estructuradas: "Mirador Natural", "Arquitectura Religiosa"…
        cls = _classify_type_hint(type_hint)
    if cls is None:
        return Verdict(False, reason="el nombre no empieza por un tipo de sitio")
    if cls.category in EXCLUDED_CATEGORIES:
        return Verdict(False, reason=f"categoría excluida ({cls.category})")
    if cls.needs_evidence and not heritage_source:
        if not _HERITAGE_EVIDENCE.search(f"{norm} {normalize(text)}"):
            return Verdict(False, reason="tipo ambiguo sin evidencia patrimonial")
    return Verdict(True, category=cls.category)


_TYPE_HINTS: list[tuple[str, str]] = [
    ("religios", "iglesias"),
    ("museo", "museos"),
    ("arqueolog", "sitios_arqueologicos"),
    ("mirador", "miradores"),
    ("area protegida", "reservas_naturales"),
    ("areas protegidas", "reservas_naturales"),
    ("monumento", "monumentos"),
    ("arte publico", "monumentos"),
    ("obra de arte", "monumentos"),
    ("espacio publico", "parques"),
    ("plaza", "plazas"),
    ("parque", "parques"),
    ("conmemorativ", "monumentos"),
    ("rio", "rios_y_balnearios"),
    ("aguas lot", "rios_y_balnearios"),
    ("aguas lent", "lagos_y_lagunas"),
    ("montana", "cerros_y_montanas"),
    ("natural", "naturaleza"),
    ("transporte", "sitios_culturales"),
    ("arquitect", "sitios_culturales"),
    ("historic", "sitios_culturales"),
    ("cultural", "sitios_culturales"),
    ("patrimonio", "sitios_culturales"),
]


def _classify_type_hint(type_hint: str) -> Optional[Classification]:
    norm = normalize(type_hint)
    for needle, category in _TYPE_HINTS:
        if needle in norm:
            return Classification(category=category, head=needle, needs_evidence=False)
    return None


# ── Extracción de datos de contacto desde el texto oficial ──────────────────

# Solo la dirección rotulada como tal ("Dirección: …"), hasta el siguiente rótulo.
_ADDRESS_RE = re.compile(
    r"direcci[oó]n\s*:\s*(.{6,120}?)"
    r"(?=\s+(?:tel[eé]fonos?|tel\b|cel(?:ular)?(?:es)?|c[oó]mo llegar|correo|e-?mail|horario|"
    r"facebook|instagram|www\.|https?:|[\w.+-]+@)|[\n;]|$)",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(
    r"(?:tel[eé]fonos?|tel|cel(?:ular)?(?:es)?|contacto)\.?\s*:?\s*(\(?\+?\d[\d\s()\-]{5,20}\d)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

# Rótulos de la plantilla de ficha de los portales: no son descripción.
_TEMPLATE_LINE = re.compile(
    r"^\s*(?:(?:direcci[oó]n|tel[eé]fonos?|tel|celular(?:es)?|c[oó]mo llegar|"
    r"correo(?: electr[oó]nico)?|e-?mail|recomendaciones|mayores informes|"
    r"horarios?(?: de atenci[oó]n)?|contacto|facebook|instagram|twitter|"
    r"p[aá]gina web|sitio web)\b.*|desde \w+\s*|https?://\S+)\s*$",
    re.IGNORECASE,
)


def extract_contact(text: str) -> dict:
    out = {}
    if m := _ADDRESS_RE.search(text or ""):
        out["address"] = " ".join(m.group(1).split()).strip(" ,")
    if m := _PHONE_RE.search(text or ""):
        out["phone"] = " ".join(m.group(1).split())
    if m := _EMAIL_RE.search(text or ""):
        out["email"] = m.group(0).rstrip(".")
    return out


def strip_template(text: str) -> str:
    """Quita las líneas de plantilla ("Dirección:", "Teléfono:", "Cómo llegar:"…)
    y deja solo la descripción propiamente dicha."""
    return "\n".join(ln for ln in (text or "").splitlines() if not _TEMPLATE_LINE.match(ln))


def clean_description(text: str, limit: int = 2000) -> str:
    t = re.sub(r"[\u200b\u00a0]+", " ", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > limit:
        cut = t[:limit]
        t = cut[: cut.rfind(". ") + 1] or cut
    return t
