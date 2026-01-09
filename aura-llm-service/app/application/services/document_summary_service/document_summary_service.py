import logging
from typing import List, Optional
from langchain_core.runnables import Runnable

from app.application.exceptions.app_exceptions import ValidationError
from app.infrastructure.llm_facade.exceptions.llm_facade_exceptions import LLMInvocationError
from app.infrastructure.llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.application.services.document_summary_service.document_summary_configuration import \
    DocumentSummaryConfiguration
from app.application.services.document_summary_service.document_summary_chunk_processor import \
    DocumentSummaryChunkProcessor
from app.application.services.document_summary_service.document_summary_configuration import SummarizationStrategy
from app.application.services.document_summary_service.document_summary_message_builder import \
    DocumentSummaryMessageBuilder
from app.application.services.document_summary_service.document_summary_request_validator import \
    DocumentSummaryRequestValidator
from app.application.services.document_summary_service.interfaces.document_summary_service_interface import \
    DocumentSummaryServiceInterface
from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import DocumentSummaryServiceError
from app.domain.dtos.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary_response import DocumentSummaryResponse
from app.infrastructure.document_context_provider.exceptions.context_provider_exception import ContextRetrievalByDocumentError
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import ContextProviderInterface

logger = logging.getLogger(__name__)


class DocumentSummaryService(DocumentSummaryServiceInterface):
    def __init__(self,
                 llm_facade: OllamaLLMFacadeInterface,
                 context_provider: ContextProviderInterface,
                 configuration: Optional[DocumentSummaryConfiguration] = None) -> None:
        self._llm_facade = llm_facade
        self._context_provider = context_provider
        self._configuration = configuration or DocumentSummaryConfiguration()

        self._validator = DocumentSummaryRequestValidator(self._configuration)

        self._llm: Optional[Runnable] = None
        self._chunk_processor: Optional[DocumentSummaryChunkProcessor] = None

        logger.info(
            "DocumentSummaryService initialized",
            extra={
                "large_document_threshold": self._configuration.large_document_threshold,
                "chunk_size": self._configuration.chunk_size,
                "max_concurrent_chunks": self._configuration.max_concurrent_chunks
            }
        )

    @classmethod
    def with_defaults(cls,
                      llm_facade: OllamaLLMFacadeInterface,
                      context_provider: ContextProviderInterface,
                      large_document_threshold: int = 5,
                      chunk_size: int = 5,
                      max_concurrent_chunks: int = 3,
                      system_prompt: Optional[str] = None) -> "DocumentSummaryService":
        configuration = DocumentSummaryConfiguration(
            large_document_threshold=large_document_threshold,
            chunk_size=chunk_size,
            max_concurrent_chunks=max_concurrent_chunks,
            system_prompt=system_prompt
        )

        return cls(
            llm_facade=llm_facade,
            context_provider=context_provider,
            configuration=configuration
        )

    async def execute_document_summary(self,
                                       document_summary_request: DocumentSummaryRequest) -> DocumentSummaryResponse:
        self._validator.validate_request(document_summary_request)

        logger.info(
            "Executing document summary",
            extra={
                "document_id": document_summary_request.document_id
            }
        )

        try:
            await self._ensure_llm_initialized()

            fragments = await self._retrieve_fragments(
                document_summary_request.document_id
            )

            if not fragments:
                logger.warning(
                    "No fragments found for document",
                    extra={
                        "document_id": document_summary_request.document_id
                    }
                )
                return DocumentSummaryResponse(
                    summary="No se encontraron fragmentos para generar el resumen."
                )

            strategy = self._configuration.select_strategy(len(fragments))

            logger.info(
                f"Using {strategy.value} strategy for {len(fragments)} fragments"
            )

            if strategy == SummarizationStrategy.MAP_REDUCE:
                summary = await self._summarize_map_reduce(fragments)
            else:
                summary = await self._summarize_direct(fragments)

            logger.info(
                "Document summary executed successfully",
                extra={
                    "document_id": document_summary_request.document_id,
                    "strategy": strategy.value,
                    "summary_length": len(summary)
                }
            )

            return DocumentSummaryResponse(summary=summary)

        except (ValidationError, ContextRetrievalByDocumentError,
                LLMInvocationError, DocumentSummaryServiceError):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during document summary execution",
                extra={
                    "error_type": type(e).__name__,
                    "document_id": document_summary_request.document_id
                }
            )
            raise DocumentSummaryServiceError("Unexpected internal error executing document summary") from e

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None and self._chunk_processor is not None:
            return

        try:
            self._llm = await self._llm_facade.get_llm_base()

            self._chunk_processor = DocumentSummaryChunkProcessor(
                configuration=self._configuration,
                llm_facade=self._llm_facade,
                llm=self._llm
            )

            logger.debug("LLM and chunk processor initialized")

        except Exception as e:
            logger.exception("Failed to initialize LLM")
            raise DocumentSummaryServiceError("Failed to initialize LLM for document summary") from e

    async def _retrieve_fragments(self,
                                  document_id: int) -> List[str]:
        logger.debug(
            "Retrieving fragments for document",
            extra={
                "document_id": document_id
            }
        )

        fragments_sequence = await self._context_provider.retrieve_fragments_by_document(
            document_id=document_id
        )

        fragments = list(fragments_sequence)

        logger.debug(
            f"Retrieved {len(fragments)} fragments",
            extra={
                "document_id": document_id, "fragments_count": len(fragments)
            }
        )

        return fragments

    async def _summarize_direct(self,
                                fragments: List[str]) -> str:
        logger.debug("Executing direct summarization")

        if self._llm is None:
            raise DocumentSummaryServiceError("LLM not initialized")

        llm_input = DocumentSummaryMessageBuilder.build_summarization_input(
            system_prompt=self._configuration.effective_system_prompt,
            fragments=fragments
        )

        summary = await self._llm_facade.call_llm_text(
            llm=self._llm,
            llm_input=llm_input
        )

        return summary

    async def _summarize_map_reduce(self,
                                    fragments: List[str]) -> str:
        logger.debug("Executing map-reduce summarization")

        if self._chunk_processor is None:
            raise DocumentSummaryServiceError("Chunk processor not initialized")

        chunks = DocumentSummaryChunkProcessor.create_chunks(
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
        logger.debug(f"Reducing {len(partial_summaries)} partial summaries into final summary")

        if self._llm is None:
            raise DocumentSummaryServiceError("LLM not initialized")

        llm_input = DocumentSummaryMessageBuilder.build_reduction_input(
            system_prompt=self._configuration.effective_system_prompt,
            partial_summaries=partial_summaries
        )

        final_summary = await self._llm_facade.call_llm_text(
            llm=self._llm,
            llm_input=llm_input
        )

        return final_summary

    @property
    def configuration(self) -> DocumentSummaryConfiguration:
        return self._configuration

    @property
    def is_llm_initialized(self) -> bool:
        return self._llm is not None
