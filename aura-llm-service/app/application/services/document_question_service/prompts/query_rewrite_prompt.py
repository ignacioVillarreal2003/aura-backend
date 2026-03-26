QUERY_REWRITE_PROMPT = """
Reformula la consulta para maximizar la recuperación de información en una base normativa.

Objetivo:
Generar una query basada en PALABRAS CLAVE, no en lenguaje natural.

Reglas:
- Mantener el significado original EXACTO
- NO agregar conceptos nuevos (ej: seguridad, estándares internacionales si no están en la consulta)
- Usar términos normativos relevantes (ej: requisitos, condiciones, documentación, autorización, aeronave, operación, sobrevuelo)
- Eliminar explicaciones o frases largas
- Priorizar keywords técnicas y jurídicas
- NO usar oraciones largas
- NO incluir prefacios como "La consulta optimizada sería", "Esta versión...", etc.
- Devuelve solo la consulta optimizada en una única línea, sin comillas

Historial:
{history}

Consulta original:
{query}

Consulta optimizada (solo keywords):
"""
