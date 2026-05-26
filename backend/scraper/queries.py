# backend/scraper/queries.py

CATEGORY_QUERIES: dict = {
    "monuments": [
        "monumentos históricos en {city}",
        "iglesias patrimonio en {city}",
        "sitios arqueológicos en {city}",
    ],
    "nature": [
        "parques naturales en {city}",
        "cascadas cerca de {city}",
        "senderos ecoturismo {city}",
    ],
    "viewpoints": [
        "miradores en {city}",
        "malecón de {city}",
        "playas y lagunas cerca de {city}",
    ],
    "cultural": [
        "barrios típicos de {city}",
        "mercados artesanales en {city}",
        "turismo cultural {city}",
    ],
}


def build_queries_for_city(city_name: str) -> list:
    """Retorna lista de {query, category} para una ciudad."""
    result = []
    for category, templates in CATEGORY_QUERIES.items():
        for template in templates:
            result.append({
                "query": template.format(city=city_name),
                "category": category,
            })
    return result
