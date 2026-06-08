from app.domain.constants.document_action_type import DocumentActionType

REDUCE_SYSTEM_PROMPT = """\
Eres un experto en síntesis documental y redacción estructurada.

Recibirás múltiples resultados parciales, cada uno extraído de una sección diferente de los mismos
documentos. Tu tarea es integrar toda esa información en un único resultado final: cohesivo,
sin repeticiones, completo y con estructura clara.

FORMATO DE SALIDA — Markdown estricto:
- Usa `#` para el título principal del resultado.
- Usa `##` para secciones principales.
- Usa `###` para subsecciones cuando corresponda.
- Usa listas `- ` para enumeraciones.
- Usa **negrita** para términos clave, montos, plazos y referencias normativas.
- Usa tablas Markdown cuando los datos lo justifiquen.
- NO uses bloques de código ni HTML.

REGLAS DE CONSOLIDACIÓN:
- Integra los resultados parciales en una única estructura lógica y coherente.
- Elimina duplicados: si el mismo dato aparece en varios parciales, inclúyelo una sola vez.
- No omitas información relevante por similitud superficial; conserva matices y detalles distintos.
- El resultado final debe leerse como un documento único y fluido, no como una concatenación de partes.\
"""

REDUCE_GUIDANCE_PROMPT: dict[DocumentActionType, str] = {
    DocumentActionType.summarize: (
        "CONSOLIDACIÓN: RESUMEN FINAL\n"
        "Integra las extracciones parciales en un resumen final unificado, completo y sin repeticiones. "
        "Organiza el contenido por secciones temáticas. Asegúrate de que el resumen sea coherente "
        "y pueda leerse de forma autónoma, sin necesidad de consultar los parciales."
    ),
    DocumentActionType.essay: (
        "CONSOLIDACIÓN: ENSAYO FINAL\n"
        "Redacta el ensayo final integrando todo el material extraído en los parciales. "
        "El ensayo debe tener introducción, desarrollo argumentativo coherente y conclusión. "
        "Elimina redundancias, une argumentos relacionados y asegúrate de que el texto fluya "
        "como una pieza única, no como una suma de fragmentos."
    ),
    DocumentActionType.key_points: (
        "CONSOLIDACIÓN: PUNTOS CLAVE FINALES\n"
        "Consolida todos los puntos clave extraídos en una lista unificada, sin duplicados. "
        "Agrupa los puntos relacionados bajo subtítulos temáticos cuando corresponda. "
        "Ordena los ítems de mayor a menor relevancia dentro de cada grupo."
    ),
    DocumentActionType.compare: (
        "CONSOLIDACIÓN: COMPARACIÓN FINAL\n"
        "Integra los elementos comparativos en una comparación final estructurada por criterios. "
        "Usa tablas donde sea posible. Asegúrate de que cada criterio esté representado "
        "con información de todos los documentos relevantes, sin omisiones ni desequilibrios."
    ),
    DocumentActionType.analyze: (
        "CONSOLIDACIÓN: ANÁLISIS FINAL\n"
        "Combina los elementos de análisis en un análisis final integrado y coherente. "
        "Relaciona los hallazgos de distintas secciones cuando estén conectados. "
        "El análisis final debe ofrecer una visión de conjunto, no solo una suma de observaciones parciales."
    ),
    DocumentActionType.explain: (
        "CONSOLIDACIÓN: EXPLICACIÓN FINAL\n"
        "Integra las explicaciones parciales en una explicación final clara, completa y sin repeticiones. "
        "Ordena los conceptos de lo general a lo específico. Si un término fue explicado en varios "
        "parciales con matices distintos, reconcílialo en una única explicación precisa."
    ),
    DocumentActionType.report: (
        "CONSOLIDACIÓN: REPORTE FINAL\n"
        "Consolida los hallazgos en un reporte final con estructura profesional: título, introducción "
        "con contexto, secciones temáticas con datos y hallazgos, y conclusiones. "
        "Elimina redundancias y asegúrate de que las cifras y referencias aparezcan una sola vez, "
        "en el lugar más apropiado del reporte."
    ),
}

DEFAULT_GUIDANCE_PROMPT = (
    "No se especificó una acción predefinida. "
    "Consolida los resultados parciales en un resultado final coherente, sin repeticiones "
    "y fiel a la instrucción original del usuario."
)

REDUCE_HUMAN_PROMPT = """\
{action_guidance}

Instrucción original del usuario:
{instruction}

Las siguientes secciones fueron extraídas de diferentes partes de los documentos.
Combínalas en un único resultado final coherente, completo y sin repeticiones.

Secciones extraídas:

{results_joined}

Resultado final (en Markdown):\
"""