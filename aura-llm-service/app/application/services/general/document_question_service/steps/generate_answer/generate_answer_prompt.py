GENERATE_ANSWER_PROMPT = """
Responde la consulta utilizando EXCLUSIVAMENTE la información del contexto.

Consulta:
{query}

Contexto:
{context}

Reglas obligatorias:
- SOLO usar información explícita del contexto
- NO inferir, interpretar ni completar información faltante
- NO agregar conocimiento externo
- Si la información es parcial, responder solo con lo disponible
- Si no hay información suficiente, responder: "No se encontró información en los documentos disponibles"

Formato de respuesta (OBLIGATORIO):
- SIEMPRE responder en formato markdown. Nunca texto plano.
- Usar encabezados, listas, negritas o tablas según corresponda
- Si aplica, listar requisitos o condiciones en forma estructurada

Prohibido:
- Generalizaciones
- Explicaciones no solicitadas

Respuesta:
"""
