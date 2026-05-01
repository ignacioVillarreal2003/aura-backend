import asyncio
import logging
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document_summary_service.constants.summarization_strategy import SummarizationStrategy
from app.application.services.document_summary_service.document_summary_settings import DocumentSummaryServiceSettings
from app.application.services.document_summary_service.document_summary_state import DocumentSummaryState
from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.application.services.document_summary_service.processors.chunk_document_summary_processor.chunk_document_summary_prompt import (
    CHUNK_SYSTEM_PROMPT,
    CHUNK_HUMAN_PROMPT,
)
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class ChunkDocumentSummaryProcessor:
    def __init__(
            self,
            document_summary_service_settings: DocumentSummaryServiceSettings,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
    ) -> None:
        self._settings = document_summary_service_settings
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._semaphore = asyncio.Semaphore(self._settings.max_concurrent_chunks)

    async def run(self, document_summary_state: DocumentSummaryState) -> None:
        if document_summary_state.strategy != SummarizationStrategy.map_reduce or not document_summary_state.fragments:
            return

        chunks = self._create_chunks(document_summary_state.fragments, self._settings.chunk_size)
        logger.debug(
            "Starting parallel chunk processing",
            extra={"chunk_count": len(chunks), "fragment_count": len(document_summary_state.fragments)},
        )

        results = await asyncio.gather(
            *[
                self._process_chunk_with_retry(chunk_index=i, chunk=chunk)
                for i, chunk in enumerate(chunks)
            ],
            return_exceptions=True,
        )

        successful, failed_count = self._separate_results(results)

        if not successful:
            logger.error("All chunks failed during map phase", extra={"failed_count": failed_count})
            raise DocumentSummaryServiceException(
                f"Failed to process any document chunk ({failed_count} failed)"
            )

        if failed_count > 0:
            logger.warning(
                "Partial chunk processing success",
                extra={"successful_count": len(successful), "failed_count": failed_count},
            )

        document_summary_state.partial_summaries = successful
        logger.debug("Map phase completed", extra={"partial_summary_count": len(successful)})

    @staticmethod
    def _create_chunks(
            fragments: list[FragmentResponse],
            chunk_size: int,
    ) -> list[list[FragmentResponse]]:
        return [fragments[i: i + chunk_size] for i in range(0, len(fragments), chunk_size)]

    async def _process_chunk_with_retry(
            self,
            chunk_index: int,
            chunk: list[FragmentResponse],
    ) -> str:
        max_attempts = self._settings.max_retry_attempts + 1
        last_error: Optional[Exception] = None

        async with self._semaphore:
            for attempt in range(max_attempts):
                try:
                    logger.debug(
                        "Processing chunk",
                        extra={
                            "chunk_index": chunk_index,
                            "attempt": attempt + 1,
                            "max_attempts": max_attempts,
                            "fragments_in_chunk": len(chunk),
                        },
                    )
                    summary = await self._summarize_chunk(chunk=chunk)
                    logger.debug(
                        "Chunk processed successfully",
                        extra={"chunk_index": chunk_index, "attempt": attempt + 1},
                    )
                    return summary

                except Exception as e:
                    last_error = e
                    is_last_attempt = attempt == max_attempts - 1
                    if not is_last_attempt:
                        logger.warning(
                            "Chunk processing failed — retrying",
                            extra={
                                "chunk_index": chunk_index,
                                "attempt": attempt + 1,
                                "error_type": type(e).__name__,
                                "retry_delay": self._settings.retry_delay,
                            },
                        )
                        await asyncio.sleep(self._settings.retry_delay)
                    else:
                        logger.error(
                            "Chunk processing failed after all attempts",
                            extra={
                                "chunk_index": chunk_index,
                                "total_attempts": max_attempts,
                                "error_type": type(e).__name__,
                            },
                        )

        raise DocumentSummaryServiceException(
            f"Failed to process chunk {chunk_index} after {max_attempts} attempt(s)"
        ) from last_error

    async def _summarize_chunk(self, chunk: list[FragmentResponse]) -> str:
        fragments_joined = "\n\n---\n\n".join(
            f"Fragmento de contexto {idx + 1}:\n{fragment.content}"
            for idx, fragment in enumerate(chunk)
        )
        llm_input = [
            SystemMessage(content=CHUNK_SYSTEM_PROMPT),
            HumanMessage(content=CHUNK_HUMAN_PROMPT.format(fragments_joined=fragments_joined)),
        ]
        llm = await self._ollama_llm_facade.get_llm_base()
        summary = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)

        if not summary or not summary.strip():
            raise DocumentSummaryServiceException("LLM returned empty summary for chunk")

        return summary.strip()

    @staticmethod
    def _separate_results(results: list) -> tuple[list[str], int]:
        successful: list[str] = []
        failed_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "Chunk failed after all retries",
                    extra={"chunk_index": i, "error_type": type(result).__name__, "error": str(result)},
                )
                failed_count += 1
            elif isinstance(result, str):
                successful.append(result)
            else:
                logger.error(
                    "Unexpected result type from chunk processing",
                    extra={"chunk_index": i, "result_type": type(result).__name__},
                )
                failed_count += 1
        return successful, failed_count
