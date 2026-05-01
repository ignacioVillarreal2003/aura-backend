import asyncio
import logging
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document_action_service.constants.processing_strategy import ProcessingStrategy
from app.application.services.document_action_service.document_action_settings import DocumentActionServiceSettings
from app.application.services.document_action_service.document_action_state import DocumentActionState
from app.application.services.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.document_action_service.processors.chunk_document_action_processor.chunk_document_action_prompt import (
    CHUNK_SYSTEM_PROMPT,
    CHUNK_HUMAN_PROMPT,
    CHUNK_GUIDANCE_PROMPT,
    DEFAULT_GUIDANCE_PROMPT,
)
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class MapChunksDocumentActionProcessor:
    def __init__(
            self,
            document_action_service_settings: DocumentActionServiceSettings,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
    ) -> None:
        self._settings = document_action_service_settings
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._semaphore = asyncio.Semaphore(self._settings.max_concurrent_chunks)

    async def run(self, state: DocumentActionState) -> None:
        if state.strategy != ProcessingStrategy.map_reduce or not state.all_fragments:
            return

        chunks = self._create_chunks(state.all_fragments, self._settings.chunk_size)
        logger.debug(
            "Starting parallel chunk processing",
            extra={"chunk_count": len(chunks), "fragment_count": len(state.all_fragments)},
        )

        results = await asyncio.gather(
            *[
                self._process_chunk_with_retry(chunk_index=i, chunk=chunk, state=state)
                for i, chunk in enumerate(chunks)
            ],
            return_exceptions=True,
        )

        successful, failed_count = self._separate_results(results)

        if not successful:
            logger.error("All chunks failed during map phase", extra={"failed_count": failed_count})
            raise DocumentActionServiceException(
                f"Failed to process any document chunk ({failed_count} failed)"
            )

        if failed_count > 0:
            logger.warning(
                "Partial chunk processing success",
                extra={"successful_count": len(successful), "failed_count": failed_count},
            )

        state.partial_results = successful
        logger.debug("Map phase completed", extra={"partial_result_count": len(successful)})

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
            state: DocumentActionState,
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
                    result = await self._process_chunk(chunk=chunk, state=state)
                    logger.debug(
                        "Chunk processed successfully",
                        extra={"chunk_index": chunk_index, "attempt": attempt + 1},
                    )
                    return result

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

        raise DocumentActionServiceException(
            f"Failed to process chunk {chunk_index} after {max_attempts} attempt(s)"
        ) from last_error

    async def _process_chunk(self, chunk: list[FragmentResponse], state: DocumentActionState) -> str:
        action_guidance = (
            CHUNK_GUIDANCE_PROMPT.get(state.action, DEFAULT_GUIDANCE_PROMPT)
            if state.action
            else DEFAULT_GUIDANCE_PROMPT
        )
        fragments_joined = "\n\n---\n\n".join(
            f"Fragmento {idx + 1} (Documento {fragment.document_id}):\n{fragment.content}"
            for idx, fragment in enumerate(chunk)
        )
        llm_input = [
            SystemMessage(content=CHUNK_SYSTEM_PROMPT),
            HumanMessage(
                content=CHUNK_HUMAN_PROMPT.format(
                    action_guidance=action_guidance,
                    instruction=state.instruction,
                    fragments_joined=fragments_joined,
                )
            ),
        ]
        llm = await self._ollama_llm_facade.get_llm_base()
        result = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)

        if not result or not result.strip():
            raise DocumentActionServiceException("LLM returned empty result for chunk")

        return result.strip()

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
