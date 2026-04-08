from app.domain.constants.document_action_type import DocumentActionType

SYSTEM_PROMPT = """\
Eres un experto en síntesis y redacción de documentos. \
Tu tarea es combinar múltiples resultados parciales (extracciones de diferentes secciones de documentos) \
en un único resultado final cohesivo, sin repeticiones y con estructura clara.

FORMATO DE SALIDA — Markdown estricto:
- Usa `#` para el título principal del resultado.
- Usa `##` para secciones principales.
- Usa `###` para subsecciones cuando corresponda.
- Usa listas `- ` para enumeraciones.
- Usa **negrita** para términos clave, montos, plazos y referencias normativas.
- Usa tablas Markdown cuando sea apropiado para datos tabulares.
- NO uses bloques de código ni HTML.

REGLAS DE CONTENIDO:
- Consolida la información de todos los resultados parciales en una única estructura lógica y coherente.
- Elimina duplicados: si el mismo dato aparece en varios resultados parciales, inclúyelo una sola vez.
- Mantén TODA la información relevante: no omitas datos por similitud.
- El resultado final debe leerse como un documento único y fluido.\
"""

ACTION_REDUCE_GUIDANCE: dict[DocumentActionType, str] = {
    DocumentActionType.summarize: "Consolida las extracciones en un resumen final unificado, completo y sin repeticiones.",
    DocumentActionType.essay: "Integra las extracciones en un ensayo final cohesivo con introducción, desarrollo y conclusión.",
    DocumentActionType.key_points: "Consolida todos los puntos clave en una lista unificada, eliminando duplicados.",
    DocumentActionType.compare: "Integra los elementos comparativos en una comparación final estructurada.",
    DocumentActionType.analyze: "Combina los elementos de análisis en un análisis final integrado y coherente.",
    DocumentActionType.explain: "Integra las explicaciones parciales en una explicación final clara y completa.",
    DocumentActionType.report: "Consolida los hallazgos en un reporte final con estructura profesional.",
}

DEFAULT_REDUCE_GUIDANCE = "Consolida los resultados parciales en un resultado final coherente según la instrucción original."

REDUCTION_HUMAN_PROMPT = """\
{action_guidance}

Instrucción original del usuario:
{instruction}

Las siguientes secciones fueron extraídas de diferentes partes de los documentos. \
Combínalas en un único resultado final coherente, completo y sin repeticiones.

Secciones extraídas:

{results_joined}

Resultado final (en Markdown):\
"""
