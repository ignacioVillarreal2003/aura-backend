CONTEXT_SELECTION_PROMPT = """
Selecciona los fragmentos más relevantes para responder la consulta.

Consulta:
{query}

Fragmentos:
{chunks}

Devuelve solo los IDs o textos más relevantes (máximo 3-5).
Prioriza precisión, no cantidad.
"""