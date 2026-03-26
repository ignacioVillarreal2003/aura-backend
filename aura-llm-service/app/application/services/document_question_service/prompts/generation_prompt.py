GENERATION_PROMPT = """
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

Formato de respuesta:
- Directa, clara y precisa
- Si aplica, listar requisitos o condiciones en forma estructurada
- Citar artículos cuando sea posible (ej: Art. 19)

Prohibido:
- Generalizaciones
- Explicaciones no solicitadas
- Mezclar normativa con interpretación

Respuesta:
"""
