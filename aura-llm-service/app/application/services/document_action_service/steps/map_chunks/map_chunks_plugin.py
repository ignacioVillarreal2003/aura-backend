import asyncio
import logging
from typing import List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document_action_service.constants.processing_strategy import ProcessingStrategy
from app.application.services.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.document_action_service.interfaces.document_action_plugin_interface import (
    DocumentActionPlugin,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_resources import (
    DocumentActionPipelineResources,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_state import (
    DocumentActionPipelineState,
)
from app.application.services.document_action_service.steps.map_chunks.map_chunks_prompt import (
    ACTION_CHUNK_GUIDANCE,
    CHUNK_HUMAN_PROMPT,
    DEFAULT_CHUNK_GUIDANCE,
    SYSTEM_PROMPT,
)
from app.application.services.document_action_service.steps.map_chunks.map_chunks_settings import (
    MapActionChunksSettings,
)
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse

logger = logging.getLogger(__name__)


class MapChunksPlugin(DocumentActionPlugin):
    def __init__(self, map_chunks_settings: Optional[MapActionChunksSettings] = None) -> None:
        self._settings = map_chunks_settings or MapActionChunksSettings()
        self._semaphore = asyncio.Semaphore(self._settings.max_concurrent_chunks)

    @property
    def plugin_name(self) -> str:
        return "map_chunks"

    def should_run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> bool:
        return state.strategy == ProcessingStrategy.map_reduce and bool(state.all_fragments)

    async def run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> None:
        chunks = self._create_chunks(state.all_fragments, self._settings.chunk_size)
        logger.debug(
            "Starting parallel chunk processing",
            extra={"chunk_count": len(chunks), "fragment_count": len(state.all_fragments)},
        )

        results = await asyncio.gather(
            *[
                self._process_chunk_with_retry(
                    chunk_index=i,
                    chunk=chunk,
                    state=state,
                    resources=resources,
                )
                for i, chunk in enumerate(chunks)
            ],
            return_exceptions=True,
        )

        successful, failed_count = self._separate_results(results)

        if not successful:
            logger.error(
                "All chunks failed during map phase",
                extra={"failed_count": failed_count},
            )
            raise DocumentActionServiceException(
                f"Failed to process any document chunk ({failed_count} failed)"
            )

        if failed_count > 0:
            logger.warning(
                "Partial chunk processing success",
                extra={"successful_count": len(successful), "failed_count": failed_count},
            )

        state.partial_results = successful
        logger.debug(
            "Map phase completed",
            extra={"partial_result_count": len(successful)},
        )

    @staticmethod
    def _create_chunks(
            fragments: List[FragmentResponse],
            chunk_size: int,
    ) -> List[List[FragmentResponse]]:
        return [
            fragments[i: i + chunk_size]
            for i in range(0, len(fragments), chunk_size)
        ]

    async def _process_chunk_with_retry(
            self,
            chunk_index: int,
            chunk: List[FragmentResponse],
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
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
                    result = await self._process_chunk(
                        chunk=chunk, state=state, resources=resources,
                    )
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

    async def _process_chunk(
            self,
            chunk: List[FragmentResponse],
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> str:
        action_guidance = (
            ACTION_CHUNK_GUIDANCE.get(state.action, DEFAULT_CHUNK_GUIDANCE)
            if state.action
            else DEFAULT_CHUNK_GUIDANCE
        )

        fragments_joined = "\n\n---\n\n".join(
            f"Fragmento {idx + 1} (Documento {fragment.document_id}):\n{fragment.content}"
            for idx, fragment in enumerate(chunk)
        )

        llm_input = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=CHUNK_HUMAN_PROMPT.format(
                    action_guidance=action_guidance,
                    instruction=state.instruction,
                    fragments_joined=fragments_joined,
                )
            ),
        ]

        llm = await resources.ollama_llm_facade.get_llm_base()
        result = await resources.llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)

        if not result or not result.strip():
            raise DocumentActionServiceException("LLM returned empty result for chunk")

        return result.strip()

    @staticmethod
    def _separate_results(results: list) -> Tuple[List[str], int]:
        successful: List[str] = []
        failed_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "Chunk failed after all retries",
                    extra={
                        "chunk_index": i,
                        "error_type": type(result).__name__,
                        "error": str(result),
                    },
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
