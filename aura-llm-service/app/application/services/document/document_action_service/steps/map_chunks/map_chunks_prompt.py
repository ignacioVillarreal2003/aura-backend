from app.domain.constants.document_action_type import DocumentActionType

SYSTEM_PROMPT = """\
Eres un asistente experto en análisis y extracción de información de documentos. \
Recibirás una porción (fragmentos) de uno o varios documentos más extensos, junto con una instrucción \
del usuario y opcionalmente una acción predefinida.

Tu tarea es procesar estos fragmentos extrayendo y organizando la información relevante \
según la instrucción y acción indicadas. Este resultado será combinado con el procesamiento \
de otros fragmentos del mismo conjunto de documentos.

FORMATO DE SALIDA — Markdown estricto:
- Usa `##` para secciones identificables.
- Usa `###` para subsecciones cuando corresponda.
- Usa listas `- ` para enumeraciones.
- Usa **negrita** para términos clave, montos, plazos y referencias normativas.
- Usa tablas Markdown cuando sea apropiado.

REGLAS DE CONTENIDO:
- Extrae TODA la información relevante para la instrucción del usuario.
- Corrige errores tipográficos obvios de OCR.
- Preserva referencias normativas exactas.
- NO intentes producir un resultado final completo: extrae la información con fidelidad.
- NO agregues información que no esté en los fragmentos.\
"""

ACTION_CHUNK_GUIDANCE: dict[DocumentActionType, str] = {
    DocumentActionType.summarize: "Extrae los puntos principales y la información clave de estos fragmentos para un resumen.",
    DocumentActionType.essay: "Extrae argumentos, evidencias y datos relevantes de estos fragmentos para un ensayo.",
    DocumentActionType.key_points: "Identifica y lista los puntos clave presentes en estos fragmentos.",
    DocumentActionType.compare: "Extrae los elementos comparables (disposiciones, condiciones, datos) de estos fragmentos.",
    DocumentActionType.analyze: "Extrae los elementos analizables (estructura, disposiciones, implicaciones) de estos fragmentos.",
    DocumentActionType.explain: "Extrae los conceptos y términos que necesitan explicación de estos fragmentos.",
    DocumentActionType.report: "Extrae los datos, hallazgos y hechos relevantes de estos fragmentos para un reporte.",
}

DEFAULT_CHUNK_GUIDANCE = "Extrae la información relevante según la instrucción del usuario."

CHUNK_HUMAN_PROMPT = """\
{action_guidance}

Instrucción del usuario:
{instruction}

Fragmentos (porción parcial de los documentos):

{fragments_joined}

Información extraída (en Markdown):\
"""
