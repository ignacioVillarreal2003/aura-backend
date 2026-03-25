QUERY_REWRITE_PROMPT = """
Dada la conversación previa y la consulta actual, genera una consulta optimizada para búsqueda, reformúlala para mejorar 
la búsqueda en una base de conocimiento.

- Mantener el significado original
- Expandir siglas si es posible
- Incluir términos técnicos relevantes
- Generar una versión clara y específica

Historial:
{history}

Consulta actual:
{query}

Consulta optimizada:
"""
