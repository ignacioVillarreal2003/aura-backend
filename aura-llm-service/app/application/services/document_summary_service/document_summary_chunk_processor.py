import asyncio
import logging
from typing import List, Optional
from langchain_core.runnables import Runnable

from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceError
)
from app.infrastructure.ollama_llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.application.services.document_summary_service.document_summary_configuration import (
    DocumentSummaryConfiguration
)
from app.application.services.document_summary_service.document_summary_prompt_builder import (
    DocumentSummaryPromptBuilder
)

logger = logging.getLogger(__name__)


class DocumentSummaryChunkProcessor:
    def __init__(self,
                 configuration: DocumentSummaryConfiguration,
                 ollama_llm_facade: OllamaLLMFacadeInterface,
                 document_summary_prompt_builder: DocumentSummaryPromptBuilder,
                 llm: Runnable) -> None:
        self._configuration = configuration
        self._ollama_llm_facade = ollama_llm_facade
        self._document_summary_prompt_builder = document_summary_prompt_builder
        self._llm = llm

        self._semaphore = asyncio.Semaphore(configuration.max_concurrent_chunks)

        logger.debug(
            "DocumentSummaryChunkProcessor initialized",
            extra={
                "max_concurrent_chunks": configuration.max_concurrent_chunks,
                "max_retry_attempts": configuration.max_retry_attempts,
                "retry_delay": configuration.retry_delay
            }
        )

    async def process_chunks(self,
                             chunks: List[List[str]]) -> List[str]:
        logger.info(
            "Starting parallel chunk processing",
            extra={
                "total_chunks": len(chunks),
                "max_concurrent": self._configuration.max_concurrent_chunks
            }
        )

        results = await asyncio.gather(
            *[self._process_single_chunk_with_retry(i, chunk) for i, chunk in enumerate(chunks)],
            return_exceptions=True
        )

        successful_summaries, failed_count = self._separate_results(results)

        if not successful_summaries:
            error_msg = f"Failed to process any chunks (all {failed_count} failed)"
            logger.error(error_msg)
            raise DocumentSummaryServiceError(error_msg)

        if failed_count > 0:
            logger.warning(
                "Partial processing success",
                extra={
                    "successful": len(successful_summaries),
                    "failed": failed_count,
                    "success_rate": f"{len(successful_summaries) / len(chunks):.1%}"
                }
            )

        logger.info(
            "Chunk processing completed",
            extra={
                "successful_chunks": len(successful_summaries),
                "failed_chunks": failed_count
            }
        )

        return successful_summaries

    @staticmethod
    def _separate_results(results: List) -> tuple[List[str], int]:
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
                    extra={
                        "chunk_index": i,
                        "result_type": type(result).__name__
                    }
                )
                failed_count += 1

        return successful_summaries, failed_count

    async def _process_single_chunk_with_retry(self,
                                               chunk_index: int,
                                               chunk: List[str]) -> str:
        async with self._semaphore:
            last_error: Optional[Exception] = None

            for attempt in range(self._configuration.max_retry_attempts):
                try:
                    logger.debug(
                        "Processing chunk",
                        extra={
                            "chunk_index": chunk_index,
                            "attempt": attempt + 1,
                            "max_attempts": self._configuration.max_retry_attempts,
                            "fragments_in_chunk": len(chunk)
                        }
                    )

                    summary = await self._process_chunk(chunk)

                    logger.debug(
                        "Chunk processed successfully",
                        extra={
                            "chunk_index": chunk_index,
                            "attempt": attempt + 1,
                            "summary_length": len(summary)
                        }
                    )

                    return summary

                except Exception as e:
                    last_error = e

                    if attempt < self._configuration.max_retry_attempts - 1:
                        logger.warning(
                            "Chunk processing failed, retrying",
                            extra={
                                "chunk_index": chunk_index,
                                "attempt": attempt + 1,
                                "error_type": type(e).__name__,
                                "error": str(e),
                                "retry_delay": self._configuration.retry_delay
                            }
                        )
                        await asyncio.sleep(self._configuration.retry_delay)
                    else:
                        logger.error(
                            "Chunk processing failed after all retries",
                            extra={
                                "chunk_index": chunk_index,
                                "total_attempts": self._configuration.max_retry_attempts,
                                "error_type": type(e).__name__,
                                "error": str(e)
                            }
                        )

            raise DocumentSummaryServiceError(
                f"Failed to process chunk {chunk_index} after {self._configuration.max_retry_attempts} attempts"
            ) from last_error

    async def _process_chunk(self, chunk: List[str]) -> str:
        llm_input = self._document_summary_prompt_builder.build_summarization_messages(
            system_prompt=self._configuration.system_prompt,
            fragments=chunk
        )

        summary = await self._ollama_llm_facade.call_llm_text(
            llm=self._llm,
            llm_input=llm_input
        )

        if not summary or not summary.strip():
            raise DocumentSummaryServiceError("LLM returned empty summary for chunk")

        return summary.strip()

    @staticmethod
    def create_chunks(fragments: List[str], chunk_size: int) -> List[List[str]]:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size debe ser positivo, se recibió: {chunk_size}")

        if not fragments:
            logger.warning("create_chunks called with empty fragments list")
            return []

        chunks = [
            fragments[i:i + chunk_size]
            for i in range(0, len(fragments), chunk_size)
        ]

        logger.debug(
            "Chunks created",
            extra={
                "total_fragments": len(fragments),
                "chunk_size": chunk_size,
                "total_chunks": len(chunks),
                "last_chunk_size": len(chunks[-1]) if chunks else 0
            }
        )

        return chunks
