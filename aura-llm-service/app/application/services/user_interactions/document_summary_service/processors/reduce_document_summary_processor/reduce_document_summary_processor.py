import logging
from collections.abc import AsyncIterator
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.user_interactions.document_summary_service.document_summary_state import DocumentSummaryState
from app.application.services.user_interactions.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.application.services.user_interactions.document_summary_service.processors.reduce_document_summary_processor.reduce_document_summary_prompt import (
    REDUCE_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
)
from app.application.services.generation_shared.prompt_augmentation import augment_system_prompt
from app.domain.dtos.user_interactions.document_summary.document_summary_stream_events import DocumentSummaryStreamDelta
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

logger = logging.getLogger(__name__)


class ReduceDocumentSummaryProcessor:
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
        partial_summaries = document_summary_state.partial_summaries
        summaries_joined = "\n\n---\n\n".join(
            f"Resumen parcial {idx + 1}:\n{summary}"
            for idx, summary in enumerate(partial_summaries)
        )
        system_content = augment_system_prompt(
            REDUCE_SYSTEM_PROMPT,
            document_summary_state.system_prompt,
            document_summary_state.response_style,
        )
        return [
            SystemMessage(content=system_content),
            HumanMessage(content=REDUCE_HUMAN_PROMPT.format(summaries_joined=summaries_joined)),
        ]

    async def run(self, document_summary_state: DocumentSummaryState) -> None:
        if not document_summary_state.partial_summaries:
            return

        partial_summaries = document_summary_state.partial_summaries

        if len(partial_summaries) == 1:
            logger.debug("Single partial summary — skipping LLM reduction step")
            document_summary_state.summary = partial_summaries[0]
            return

        logger.debug("Reducing partial summaries", extra={"partial_summary_count": len(partial_summaries)})

        llm_input = self._build_llm_input(document_summary_state)

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except Exception as e:
            logger.exception("Reduction LLM call failed")
            raise DocumentSummaryServiceException(
                "Error combining partial summaries into the final summary"
            ) from e

        summary = raw.strip() if raw else ""
        if not summary:
            logger.warning("LLM returned empty result during reduction")
            raise DocumentSummaryServiceException("The model did not generate a valid final summary")

        document_summary_state.summary = summary
        logger.debug("Reduction completed successfully")

    async def stream(
            self,
            document_summary_state: DocumentSummaryState,
    ) -> AsyncIterator[DocumentSummaryStreamDelta]:
        if not document_summary_state.partial_summaries:
            return

        partial_summaries = document_summary_state.partial_summaries

        if len(partial_summaries) == 1:
            logger.debug("Single partial summary — skipping LLM reduction step (stream)")
            document_summary_state.summary = partial_summaries[0]
            yield DocumentSummaryStreamDelta(text=partial_summaries[0])
            return

        logger.debug("Reducing partial summaries (stream)", extra={"partial_summary_count": len(partial_summaries)})

        llm_input = self._build_llm_input(document_summary_state)

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            async for delta in self._ollama_llm_streaming_invoker.stream_llm_content(llm, llm_input):
                document_summary_state.summary += delta
                yield DocumentSummaryStreamDelta(text=delta)
        except Exception as e:
            logger.exception("Reduction streaming failed")
            raise DocumentSummaryServiceException(
                "Error combining partial summaries into the final summary"
            ) from e

        if not document_summary_state.summary.strip():
            logger.warning("LLM stream produced no visible text during reduction; falling back to non-stream")
            try:
                llm = await self._ollama_llm_facade.get_llm_base()
                raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
            except Exception as e:
                logger.exception("Reduction non-stream fallback failed")
                raise DocumentSummaryServiceException(
                    "Error combining partial summaries into the final summary"
                ) from e
            if raw and raw.strip():
                document_summary_state.summary = raw.strip()
                yield DocumentSummaryStreamDelta(text=document_summary_state.summary)

        logger.debug("Reduction (stream) completed")
