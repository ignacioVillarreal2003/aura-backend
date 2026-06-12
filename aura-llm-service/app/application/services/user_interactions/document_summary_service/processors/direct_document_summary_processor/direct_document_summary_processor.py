import logging
from collections.abc import AsyncIterator
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.user_interactions.document_summary_service.constants.summarization_strategy import SummarizationStrategy
from app.application.services.user_interactions.document_summary_service.document_summary_state import DocumentSummaryState
from app.application.services.user_interactions.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.application.services.user_interactions.document_summary_service.processors.direct_document_summary_processor.direct_document_summary_prompt import (
    DIRECT_HUMAN_PROMPT,
    DIRECT_SYSTEM_PROMPT,
)
from app.application.services.generation_shared.prompts.prompt_augmentation import augment_system_prompt
from app.domain.dtos.user_interactions.document_summary.document_summary_stream_events import DocumentSummaryStreamDelta
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

logger = logging.getLogger(__name__)


class DirectDocumentSummaryProcessor:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._ollama_llm_streaming_invoker = ollama_llm_streaming_invoker

    def _build_llm_input(self, document_summary_state: DocumentSummaryState) -> list:
        fragments_joined = "\n\n---\n\n".join(
            f"Fragmento de contexto {idx + 1}:\n{fragment.content}"
            for idx, fragment in enumerate(document_summary_state.fragments)
        )
        system_content = augment_system_prompt(
            DIRECT_SYSTEM_PROMPT,
            document_summary_state.system_prompt,
            document_summary_state.response_style,
        )
        return [
            SystemMessage(content=system_content),
            HumanMessage(content=DIRECT_HUMAN_PROMPT.format(fragments=fragments_joined)),
        ]

    async def run(self, document_summary_state: DocumentSummaryState) -> None:
        if document_summary_state.strategy != SummarizationStrategy.direct or not document_summary_state.fragments:
            return

        logger.debug(
            "Executing direct summarization",
            extra={"fragment_count": len(document_summary_state.fragments)},
        )

        llm_input = self._build_llm_input(document_summary_state)

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

    async def stream(
            self,
            document_summary_state: DocumentSummaryState,
    ) -> AsyncIterator[DocumentSummaryStreamDelta]:
        if document_summary_state.strategy != SummarizationStrategy.direct or not document_summary_state.fragments:
            return

        logger.debug(
            "Executing direct summarization (stream)",
            extra={"fragment_count": len(document_summary_state.fragments)},
        )

        llm_input = self._build_llm_input(document_summary_state)

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            async for delta in self._ollama_llm_streaming_invoker.stream_llm_content(llm, llm_input):
                document_summary_state.summary += delta
                yield DocumentSummaryStreamDelta(text=delta)
        except Exception as e:
            logger.exception("Direct summarization streaming failed")
            raise DocumentSummaryServiceException("Error generating the document summary") from e

        if not document_summary_state.summary.strip():
            logger.warning("LLM stream produced no visible text in direct mode; falling back to non-stream")
            try:
                llm = await self._ollama_llm_facade.get_llm_base()
                raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
            except Exception as e:
                logger.exception("Direct summarization non-stream fallback failed")
                raise DocumentSummaryServiceException("Error generating the document summary") from e
            if raw and raw.strip():
                document_summary_state.summary = raw.strip()
                yield DocumentSummaryStreamDelta(text=document_summary_state.summary)

        logger.debug("Direct summarization (stream) completed")
