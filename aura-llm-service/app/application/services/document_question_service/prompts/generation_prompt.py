GENERATION_PROMPT = """
Responde la consulta utilizando únicamente la información proporcionada en el contexto.

Consulta:
{query}

Contexto:
{context}

Reglas:
- No inventar información
- Si no está en el contexto, decir: "No se encontró información en los documentos disponibles"
- Responder de forma clara, formal y precisa
- Priorizar normativa, procedimientos y documentos oficiales

Respuesta:
"""