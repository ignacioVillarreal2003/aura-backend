import logging
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document_summary_service.document_summary_state import DocumentSummaryState
from app.application.services.document_summary_service.processors.fallback_document_summary_processor.fallback_document_summary_prompt import (
    FALLBACK_HUMAN_PROMPT,
    FALLBACK_SYSTEM_PROMPT,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_STATIC_FALLBACK_MESSAGE = (
    "No se encontró información suficiente en el documento para generar un resumen. "
    "Verifique que el documento esté correctamente cargado en el sistema o contacte al administrador."
)


class FallbackDocumentSummaryProcessor:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    async def run(self, document_summary_state: DocumentSummaryState) -> None:
        if document_summary_state.summary:
            return

        logger.warning(
            "No summary was generated — applying fallback",
            extra={
                "document_id": document_summary_state.document_id,
                "fragment_count": len(document_summary_state.fragments),
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
                document_summary_state.summary = answer.strip()
                return
        except Exception:
            logger.warning("Fallback summary generation failed, returning static message", exc_info=True)

        document_summary_state.summary = _STATIC_FALLBACK_MESSAGE
