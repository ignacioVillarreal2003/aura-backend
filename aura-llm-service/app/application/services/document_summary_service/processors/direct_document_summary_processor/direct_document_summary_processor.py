import logging
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document_summary_service.constants.summarization_strategy import SummarizationStrategy
from app.application.services.document_summary_service.document_summary_state import DocumentSummaryState
from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.application.services.document_summary_service.processors.direct_document_summary_processor.direct_document_summary_prompt import (
    DIRECT_HUMAN_PROMPT,
    DIRECT_SYSTEM_PROMPT,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class DirectDocumentSummaryProcessor:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    async def run(self, document_summary_state: DocumentSummaryState) -> None:
        if document_summary_state.strategy != SummarizationStrategy.direct or not document_summary_state.fragments:
            return

        logger.debug(
            "Executing direct summarization",
            extra={"fragment_count": len(document_summary_state.fragments)},
        )

        fragments_joined = "\n\n---\n\n".join(
            f"Fragmento de contexto {idx + 1}:\n{fragment.content}"
            for idx, fragment in enumerate(document_summary_state.fragments)
        )
        llm_input = [
            SystemMessage(content=DIRECT_SYSTEM_PROMPT),
            HumanMessage(content=DIRECT_HUMAN_PROMPT.format(fragments=fragments_joined)),
        ]

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except Exception as e:
            logger.exception("Direct summarization LLM call failed")
            raise DocumentSummaryServiceException("Error generating the document summary") from e

        summary = raw.strip() if raw else ""
        if not summary:
            logger.warning("LLM returned empty summary in direct mode")
            raise DocumentSummaryServiceException("The model did not generate a valid summary")

        document_summary_state.summary = summary
        logger.debug("Direct summarization completed successfully")
