CONTEXT_SELECTION_PROMPT = """
Selecciona los fragmentos más relevantes para responder la consulta.

Consulta:
{query}

Fragmentos:
{chunks}

Devuelve SOLO un JSON array de enteros con índices 0-based, correspondientes a los fragmentos seleccionados.
No devuelvas texto adicional.
Ejemplo: [0,2]

Usa como máximo {max_fragments} índices.
Prioriza precisión, no cantidad.
"""