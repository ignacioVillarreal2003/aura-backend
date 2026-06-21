import logging
import json
from langchain_core.messages import SystemMessage, HumanMessage

from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.application.services.user_interactions.feedback_evaluation_service.interfaces.feedback_evaluation_service_interface import FeedbackEvaluationServiceInterface
from app.domain.dtos.user_interactions.feedback_evaluation.feedback_evaluation_request import FeedbackEvaluationRequest
from app.domain.dtos.user_interactions.feedback_evaluation.feedback_evaluation_response import FeedbackEvaluationResponse

logger = logging.getLogger(__name__)

EVALUATION_SYSTEM_PROMPT = """Eres un auditor experto de sistemas conversacionales de IA. Estás evaluando una interacción que recibió una valoración negativa por parte del usuario. Tu objetivo es auditar la respuesta del asistente, clasificar el error y proponer la respuesta esperada.

Debes responder ÚNICAMENTE con un objeto JSON estructurado que contenga exactamente los siguientes campos sin envoltorios de código markdown (como ```json):
{
  "failure_category": "Clasificación del error. Debe ser exactamente uno de los valores listados abajo.",
  "failure_explanation": "Explicación concisa de dónde y por qué falló el modelo.",
  "expected_output": "La respuesta óptima y corregida que el asistente debió dar.",
  "confidence_score": Un número decimal entre 0.00 y 1.00 que indique tu seguridad del análisis.
}

Valores válidos para "failure_category":
- "retrieval_miss": La información para responder no estaba en el contexto de documentos suministrado (RAG), o el recuperador no extrajo el fragmento correcto.
- "hallucination": El modelo inventó datos o hechos que no estaban en el contexto RAG o en su conocimiento básico factual.
- "reasoning": El modelo poseía la información correcta en el contexto pero cometió un error de lógica, síntesis o cálculo.
- "style": La respuesta no respetó el tono, formato, estilo o brevedad solicitados.
- "incomplete": El modelo omitió responder una parte explícita de la pregunta o instrucción del usuario.
- "other": Falló por otra razón que no encaja en las categorías anteriores.
- "no_failure": La valoración del usuario es injustificada; la respuesta de la IA era correcta y completa.
"""

EVALUATION_HUMAN_PROMPT_TEMPLATE = """--- CONTEXTO DE LA INTERACCIÓN ---
Consulta del usuario: {user_query}
Historial de conversación reciente: {chat_history}
Contexto recuperado de RAG (fragmentos): {fragments}
Respuesta generada por la IA: {assistant_response}
Motivo de error reportado por el usuario: {feedback_reason}
Comentario detallado del usuario: {feedback_comment}
Modo de ejecución: {mode}

Por favor, audita esta interacción y provee tu veredicto en formato JSON según el esquema indicado.
"""


class FeedbackEvaluationService(FeedbackEvaluationServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    async def execute_feedback_evaluation(
            self,
            request: FeedbackEvaluationRequest,
    ) -> FeedbackEvaluationResponse:
        logger.info("Executing feedback evaluation (LLM-as-a-judge)")

        # Retrieve JSON mode model
        llm = await self._ollama_llm_facade.get_llm_json()

        # Format inputs
        chat_history_str = json.dumps(request.chat_history, ensure_ascii=False, indent=2)
        fragments_str = json.dumps(request.fragments, ensure_ascii=False, indent=2)

        human_content = EVALUATION_HUMAN_PROMPT_TEMPLATE.format(
            user_query=request.user_query,
            chat_history=chat_history_str,
            fragments=fragments_str,
            assistant_response=request.assistant_response,
            feedback_reason=request.feedback_reason or "N/A",
            feedback_comment=request.feedback_comment or "N/A",
            mode=request.mode,
        )

        messages = [
            SystemMessage(content=EVALUATION_SYSTEM_PROMPT),
            HumanMessage(content=human_content)
        ]

        # Call LLM
        response_text = await self._ollama_llm_invoker.call_llm_content(
            llm=llm,
            llm_input=messages,
        )

        # Parse response
        try:
            # Clean possible markdown wrapping if any (just in case)
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```"):
                lines = cleaned_text.splitlines()
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    cleaned_text = "\n".join(lines[1:-1]).strip()
            
            data = json.loads(cleaned_text)
        except Exception as e:
            logger.exception("Failed to parse LLM response as JSON. Raw output: %s", response_text)
            raise ValueError(f"El LLM juez retornó una respuesta inválida (no parseable como JSON): {e}")

        # Inject model name in the response DTO
        judge_model = getattr(self._ollama_llm_facade._settings, "model_name", "judge-ollama")

        return FeedbackEvaluationResponse(
            failure_category=data.get("failure_category", "other"),
            failure_explanation=data.get("failure_explanation", "No explanation provided."),
            expected_output=data.get("expected_output", ""),
            confidence_score=float(data.get("confidence_score", 0.0)),
            judge_model=judge_model,
        )
