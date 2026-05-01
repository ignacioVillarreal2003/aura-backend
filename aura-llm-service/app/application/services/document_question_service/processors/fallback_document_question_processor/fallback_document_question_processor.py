import logging
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document_question_service.document_question_state import DocumentQuestionState
from app.application.services.document_question_service.processors.fallback_document_question_processor.fallback_document_question_prompt import (
    FALLBACK_HUMAN_PROMPT,
    FALLBACK_SYSTEM_PROMPT,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_STATIC_FALLBACK_MESSAGE = (
    "No se encontró información relevante en la base documental para responder su consulta. "
    "Por favor, reformule su pregunta o consulte directamente la documentación disponible."
)


class FallbackDocumentQuestionProcessor:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    async def run(self, document_question_state: DocumentQuestionState) -> None:
        if document_question_state.fragments and document_question_state.answer:
            return

        reason = "no context retrieved" if not document_question_state.fragments else "answer was empty or insufficient"
        logger.debug("Fallback triggered", extra={"reason": reason})

        try:
            llm_input = [
                SystemMessage(content=FALLBACK_SYSTEM_PROMPT),
                HumanMessage(
                    content=FALLBACK_HUMAN_PROMPT.format(
                        question=document_question_state.current_message.content
                    )
                ),
            ]
            llm = await self._ollama_llm_facade.get_llm_base()
            answer = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)

            if answer and answer.strip():
                document_question_state.answer = answer.strip()
                return
        except Exception:
            logger.warning("Fallback generation failed, returning static message", exc_info=True)

        document_question_state.answer = _STATIC_FALLBACK_MESSAGE
