import logging
from typing import List, Optional
from langchain_core.runnables import Runnable

from app.application.services.document_summary_service.constants.summarization_strategy import SummarizationStrategy
from app.application.services.document_summary_service.document_summary_chunk_processor import (
    DocumentSummaryChunkProcessor
)
from app.application.services.document_summary_service.document_summary_configuration import (
    DocumentSummaryConfiguration
)
from app.application.services.document_summary_service.document_summary_prompt_builder import (
    DocumentSummaryPromptBuilder
)
from app.application.services.document_summary_service.document_summary_request_validator import (
    DocumentSummaryRequestValidator
)
from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceError
)
from app.application.services.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface
)
from app.domain.dtos.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary_response import DocumentSummaryResponse
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface
)
from app.infrastructure.ollama_llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class DocumentSummaryService(DocumentSummaryServiceInterface):
    def __init__(self,
                 ollama_llm_facade: OllamaLLMFacadeInterface,
                 document_context_provider: DocumentContextProviderInterface,
                 configuration: Optional[DocumentSummaryConfiguration] = None) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._document_context_provider = document_context_provider
        self._configuration = configuration or DocumentSummaryConfiguration()

        self._request_validator = DocumentSummaryRequestValidator(self._configuration)
        self._prompt_builder = DocumentSummaryPromptBuilder()

        self._llm: Optional[Runnable] = None
        self._chunk_processor: Optional[DocumentSummaryChunkProcessor] = None
        self._llm_initialization_failed = False

        logger.info("DocumentSummaryService initialized")

    @classmethod
    def create(cls,
               ollama_llm_facade: OllamaLLMFacadeInterface,
               document_context_provider: DocumentContextProviderInterface,
               large_document_threshold: Optional[int] = None,
               chunk_size: Optional[int] = None,
               max_concurrent_chunks: Optional[int] = None,
               max_retry_attempts: Optional[int] = None,
               retry_delay: Optional[float] = None,
               custom_system_prompt: Optional[str] = None) -> "DocumentSummaryService":
        config_kwargs = {}

        if large_document_threshold is not None:
            config_kwargs['large_document_threshold'] = large_document_threshold
        if chunk_size is not None:
            config_kwargs['chunk_size'] = chunk_size
        if max_concurrent_chunks is not None:
            config_kwargs['max_concurrent_chunks'] = max_concurrent_chunks
        if max_retry_attempts is not None:
            config_kwargs['max_retry_attempts'] = max_retry_attempts
        if retry_delay is not None:
            config_kwargs['retry_delay'] = retry_delay
        if custom_system_prompt is not None:
            config_kwargs['custom_system_prompt'] = custom_system_prompt

        configuration = DocumentSummaryConfiguration(**config_kwargs)

        return cls(
            ollama_llm_facade=ollama_llm_facade,
            document_context_provider=document_context_provider,
            configuration=configuration
        )

    async def execute_document_summary(self,
                                       request: DocumentSummaryRequest) -> DocumentSummaryResponse:
        logger.info(
            "Starting document summary execution",
            extra={
                "document_id": request.document_id
            }
        )

        self._request_validator.validate_request(request)

        context_fragments = await self.retrieve_context_fragments_by_document(request.document_id)

        if not context_fragments:
            logger.warning(
                "No fragments found for document",
                extra={
                    "document_id": request.document_id
                }
            )
            return DocumentSummaryResponse(
                summary="No se encontraron fragmentos para generar el resumen."
            )

        summary = await self.generate_summary(
            context_fragments=context_fragments
        )

        logger.info(
            "Document summary executed successfully",
            extra={
                "document_id": request.document_id,
                "context_fragments": context_fragments,
                "summary": summary
            }
        )

        return DocumentSummaryResponse(
            summary=summary
        )

    async def retrieve_context_fragments_by_document(self,
                                                     document_id: int) -> List[str]:
        logger.debug(
            "Retrieving fragments for document",
            extra={
                "document_id": document_id
            }
        )

        try:
            fragments = await self._document_context_provider.retrieve_context_fragments_by_document(
                document_id=document_id
            )

            logger.info(
                "Fragments retrieved successfully",
                extra={
                    "document_id": document_id,
                    "fragments_count": len(fragments)
                }
            )

            return fragments

        except Exception as e:
            logger.exception(
                "Unexpected error retrieving fragments",
                extra={
                    "error_type": type(e).__name__,
                    "document_id": document_id
                }
            )
            raise DocumentSummaryServiceError("Error inesperado al recuperar fragmentos del documento") from e

    async def generate_summary(self,
                               context_fragments: List[str]) -> str:
        strategy = self._configuration.select_strategy(len(context_fragments))

        logger.info(
            "Generating summary",
            extra={
                "strategy": strategy.value,
                "context_fragments": len(context_fragments),
                "threshold": self._configuration.large_document_threshold
            }
        )

        try:
            await self._ensure_llm_initialized()

            if strategy == SummarizationStrategy.MAP_REDUCE:
                summary = await self._summarize_map_reduce(context_fragments)
            else:
                summary = await self._summarize_direct(context_fragments)

            if not summary or not summary.strip():
                logger.warning("Generated empty summary")
                raise DocumentSummaryServiceError("El modelo no generó un resumen válido")

            logger.info(
                "Summary generated successfully",
                extra={
                    "strategy": strategy.value,
                    "summary": summary
                }
            )

            return summary.strip()

        except Exception as e:
            logger.exception(
                "Unexpected error during summary generation",
                extra={
                    "error_type": type(e).__name__,
                    "strategy": strategy.value
                }
            )
            raise DocumentSummaryServiceError("Error inesperado al generar el resumen") from e

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None and self._chunk_processor is not None:
            return

        if self._llm_initialization_failed:
            raise DocumentSummaryServiceError("El modelo de lenguaje no pudo ser inicializado previamente")

        logger.debug("Initializing LLM and chunk processor")

        try:
            self._llm = await self._ollama_llm_facade.get_llm_base()

            self._chunk_processor = DocumentSummaryChunkProcessor(
                configuration=self._configuration,
                ollama_llm_facade=self._ollama_llm_facade,
                document_summary_prompt_builder=self._prompt_builder,
                llm=self._llm
            )

            logger.info("LLM and chunk processor initialized successfully")

        except Exception as e:
            self._llm_initialization_failed = True
            logger.error(
                "LLM initialization failed",
                extra={
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise DocumentSummaryServiceError("Error al inicializar el modelo de lenguaje") from e

    async def _summarize_direct(self,
                                fragments: List[str]) -> str:
        logger.debug(
            "Executing DIRECT summarization",
            extra={
                "fragments_count": len(fragments)
            }
        )

        if self._llm is None:
            raise DocumentSummaryServiceError("LLM no inicializado. Esto no debería ocurrir.")

        llm_input = self._prompt_builder.build_summarization_messages(
            system_prompt=self._configuration.system_prompt,
            fragments=fragments
        )

        summary = await self._ollama_llm_facade.call_llm_text(
            llm=self._llm,
            llm_input=llm_input
        )

        return summary

    async def _summarize_map_reduce(self,
                                    fragments: List[str]) -> str:
        logger.debug(
            "Executing MAP_REDUCE summarization",
            extra={
                "fragments_count": len(fragments),
                "chunk_size": self._configuration.chunk_size
            }
        )

        if self._chunk_processor is None:
            raise DocumentSummaryServiceError("Chunk processor no inicializado. Esto no debería ocurrir.")

        chunks = self._chunk_processor.create_chunks(
            fragments=fragments,
            chunk_size=self._configuration.chunk_size
        )

        partial_summaries = await self._chunk_processor.process_chunks(chunks)

        if len(partial_summaries) == 1:
            logger.debug("Only one partial summary, returning directly")
            return partial_summaries[0]

        final_summary = await self._reduce_summaries(partial_summaries)

        return final_summary

    async def _reduce_summaries(self,
                                partial_summaries: List[str]) -> str:
        logger.debug(
            "Reducing partial summaries",
            extra={
                "partial_summaries_count": len(partial_summaries)
            }
        )

        if self._llm is None:
            raise DocumentSummaryServiceError(
                "LLM no inicializado. Esto no debería ocurrir."
            )

        llm_input = self._prompt_builder.build_reduction_messages(
            system_prompt=self._configuration.system_prompt,
            partial_summaries=partial_summaries
        )

        final_summary = await self._ollama_llm_facade.call_llm_text(
            llm=self._llm,
            llm_input=llm_input
        )

        return final_summary
