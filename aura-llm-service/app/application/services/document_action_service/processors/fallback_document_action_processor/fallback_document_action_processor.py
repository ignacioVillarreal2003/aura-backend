import logging
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document_action_service.document_action_state import DocumentActionState
from app.application.services.document_action_service.processors.fallback_document_action_processor.fallback_document_action_prompt import (
    FALLBACK_HUMAN_PROMPT,
    FALLBACK_SYSTEM_PROMPT,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_STATIC_FALLBACK_MESSAGE = (
    "No se encontró información suficiente en los documentos para generar una respuesta. "
    "Verifique que los documentos estén correctamente cargados en el sistema o contacte al administrador."
)


class FallbackDocumentActionProcessor:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    async def run(self, state: DocumentActionState) -> None:
        if state.result:
            return

        logger.warning(
            "No result was generated — applying fallback",
            extra={
                "document_ids": state.document_ids,
                "fragment_count": len(state.all_fragments),
            },
        )

        try:
            llm_input = [
                SystemMessage(content=FALLBACK_SYSTEM_PROMPT),
                HumanMessage(content=FALLBACK_HUMAN_PROMPT),
            ]
            llm = await self._ollama_llm_facade.get_llm_base()
            answer = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)

            if answer and answer.strip():
                state.result = answer.strip()
                return
        except Exception:
            logger.warning("Fallback response generation failed, returning static message", exc_info=True)

        state.result = _STATIC_FALLBACK_MESSAGE
