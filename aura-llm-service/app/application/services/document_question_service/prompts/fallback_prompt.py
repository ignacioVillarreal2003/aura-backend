FALLBACK_PROMPT = """
El sistema no encontró información relevante en la base documental.

Genera una respuesta indicando:
- Que no hay información disponible
- Sugerir reformular la consulta
- Mantener tono profesional FAU

Consulta:
{query}
"""