import asyncio
import logging
from typing import List, Optional
from langchain_core.runnables import Runnable

from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import DocumentSummaryServiceError
from app.application.llm_facade.interfaces.llm_facade_interface import LLMFacadeInterface
from app.application.services.document_summary_service.document_summary_configuration import \
    DocumentSummaryConfiguration
from app.application.services.document_summary_service.document_summary_message_builder import \
    DocumentSummaryMessageBuilder

logger = logging.getLogger(__name__)


class DocumentSummaryChunkProcessor:
    def __init__(self,
                 configuration: DocumentSummaryConfiguration,
                 llm_facade: LLMFacadeInterface,
                 llm: Runnable):
        self._configuration = configuration
        self._llm_facade = llm_facade
        self._llm = llm
        self._semaphore = asyncio.Semaphore(configuration.max_concurrent_chunks)

    async def process_chunks(self,
                             chunks: List[List[str]]) -> List[str]:
        logger.info(
            f"Processing {len(chunks)} chunks with up to {self._configuration.max_concurrent_chunks} concurrent workers"
        )

        results = await asyncio.gather(
            *[self._process_chunk_with_retry(i, chunk) for i, chunk in enumerate(chunks)],
            return_exceptions=True
        )

        successful_summaries: List[str] = []
        failed_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    f"Chunk {i} failed after all retries",
                    extra={
                        "error": str(result)
                    }
                )
                failed_count += 1
            elif isinstance(result, str):
                successful_summaries.append(result)

        if not successful_summaries:
            raise DocumentSummaryServiceError(f"Failed to process any chunks ({failed_count} failed)")

        if failed_count > 0:
            logger.warning(f"Partial success: {len(successful_summaries)} succeeded, {failed_count} failed")

        return successful_summaries

    async def _process_chunk_with_retry(self,
                                        chunk_index: int,
                                        chunk: List[str]) -> str:
        async with self._semaphore:
            last_error: Optional[Exception] = None

            for attempt in range(self._configuration.max_retry_attempts):
                try:
                    logger.debug(f"Processing chunk {chunk_index} (attempt {attempt + 1})")

                    llm_input = DocumentSummaryMessageBuilder.build_summarization_input(
                        system_prompt=self._configuration.effective_system_prompt,
                        fragments=chunk
                    )

                    result = await self._llm_facade.call_llm_text(
                        llm=self._llm,
                        llm_input=llm_input
                    )

                    logger.debug(f"Chunk {chunk_index} processed successfully")
                    return result

                except Exception as e:
                    last_error = e

                    if attempt < self._configuration.max_retry_attempts - 1:
                        logger.warning(
                            f"Chunk {chunk_index} failed on attempt {attempt + 1}, retrying...",
                            extra={
                                "error": str(e)
                            }
                        )
                        await asyncio.sleep(self._configuration.retry_delay)
                    else:
                        logger.error(
                            f"Chunk {chunk_index} failed after {self._configuration.max_retry_attempts} attempts",
                            extra={
                                "error": str(e)
                            }
                        )

            raise DocumentSummaryServiceError(
                f"Failed to process chunk {chunk_index} after {self._configuration.max_retry_attempts} attempts"
            ) from last_error

    @staticmethod
    def create_chunks(fragments: List[str],
                      chunk_size: int) -> List[List[str]]:
        chunks = [
            fragments[i:i + chunk_size] for i in range(0, len(fragments), chunk_size)
        ]

        logger.debug(f"Split {len(fragments)} fragments into {len(chunks)} chunks of size {chunk_size}")

        return chunks
