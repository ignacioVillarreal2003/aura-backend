import asyncio
import logging
from typing import List, Optional, Tuple

from app.application.services.document_summary_service.document_summary_prompt_builder import (
    DocumentSummaryPromptBuilder
)
from app.application.services.document_summary_service.document_summary_settings import DocumentSummaryServiceSettings
from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException
)
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class DocumentSummaryChunkProcessor:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            document_summary_service_settings: DocumentSummaryServiceSettings,
            document_summary_prompt_builder: DocumentSummaryPromptBuilder,
            ollama_llm_invoker: OllamaLLMInvokerInterface
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = document_summary_service_settings
        self._prompt_builder = document_summary_prompt_builder
        self._llm_invoker = ollama_llm_invoker
        self._semaphore = asyncio.Semaphore(self._settings.max_concurrent_chunks)

        logger.debug("DocumentSummaryChunkProcessor initialized")

    @staticmethod
    def create_chunks(fragments: List[str], chunk_size: int) -> List[List[str]]:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got: {chunk_size}")

        if not fragments:
            logger.warning("create_chunks called with empty fragments list")
            return []

        return [
            fragments[i : i + chunk_size]
            for i in range(0, len(fragments), chunk_size)
        ]

    async def process_chunks(self, chunks: List[List[str]]) -> List[str]:
        logger.debug(
            "Starting parallel chunk processing",
            extra={"chunk_count": len(chunks)}
        )

        results = await asyncio.gather(
            *[self._process_single_chunk_with_retry(i, chunk) for i, chunk in enumerate(chunks)],
            return_exceptions=True
        )

        successful_summaries, failed_count = self._separate_results(results)

        if not successful_summaries:
            logger.error(
                "All chunks failed during processing",
                extra={"failed_count": failed_count},
            )
            raise DocumentSummaryServiceException(
                f"Failed to process any document chunk ({failed_count} failed)"
            )

        if failed_count > 0:
            logger.warning(
                "Partial chunk processing success",
                extra={
                    "successful_count": len(successful_summaries),
                    "failed_count": failed_count
                }
            )

        logger.debug(
            "Chunk processing completed",
            extra={"successful_count": len(successful_summaries)}
        )
        return successful_summaries

    @staticmethod
    def _separate_results(results: List) -> Tuple[List[str], int]:
        successful_summaries: List[str] = []
        failed_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "Chunk failed after all retries",
                    extra={
                        "chunk_index": i,
                        "error_type": type(result).__name__,
                        "error": str(result)
                    }
                )
                failed_count += 1
            elif isinstance(result, str):
                successful_summaries.append(result)
            else:
                logger.error(
                    "Unexpected result type from chunk processing",
                    extra={"chunk_index": i, "result_type": type(result).__name__}
                )
                failed_count += 1

        return successful_summaries, failed_count

    async def _process_single_chunk_with_retry(
            self,
            chunk_index: int,
            chunk: List[str]
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
                            "fragments_in_chunk": len(chunk)
                        }
                    )

                    summary = await self._process_chunk(chunk)

                    logger.debug(
                        "Chunk processed successfully",
                        extra={"chunk_index": chunk_index, "attempt": attempt + 1}
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
                                "retry_delay": self._settings.retry_delay
                            }
                        )
                        await asyncio.sleep(self._settings.retry_delay)
                    else:
                        logger.error(
                            "Chunk processing failed after all attempts",
                            extra={
                                "chunk_index": chunk_index,
                                "total_attempts": max_attempts,
                                "error_type": type(e).__name__
                            }
                        )

        raise DocumentSummaryServiceException(
            f"Failed to process chunk {chunk_index} after {max_attempts} attempt(s)"
        ) from last_error

    async def _process_chunk(self, chunk: List[str]) -> str:
        llm = await self._ollama_llm_facade.get_llm_base()

        llm_input = self._prompt_builder.build_summarization_messages(
            system_prompt=self._settings.system_prompt,
            fragments=chunk
        )

        summary = await self._llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)

        if not summary or not summary.strip():
            raise DocumentSummaryServiceException("LLM returned empty summary for chunk")

        return summary.strip()
