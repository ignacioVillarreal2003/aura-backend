import logging
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, Request, status

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_summary_service.constants.summarization_strategy import SummarizationStrategy
from app.application.services.document_summary_service.document_summary_chunk_processor import (
    DocumentSummaryChunkProcessor
)
from app.application.services.document_summary_service.document_summary_prompt_builder import (
    DocumentSummaryPromptBuilder
)
from app.application.services.document_summary_service.document_summary_request_validator import (
    DocumentSummaryRequestValidator
)
from app.application.services.document_summary_service.document_summary_settings import DocumentSummaryServiceSettings
from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException
)
from app.application.services.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface
)
from app.domain.dtos.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary.document_summary_response import DocumentSummaryResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface
)
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class DocumentSummaryService(DocumentSummaryServiceInterface):
    _KNOWN_EXCEPTIONS = (
        RequestValidationException,
        DocumentSummaryServiceException
    )

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            document_summary_service_settings: Optional[DocumentSummaryServiceSettings] = None
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._llm_invoker = llm_invoker
        self._document_context_provider = document_context_provider
        self._settings = document_summary_service_settings or DocumentSummaryServiceSettings()

        self._prompt_builder = DocumentSummaryPromptBuilder()
        self._request_validator = DocumentSummaryRequestValidator(
            document_summary_service_settings=self._settings
        )
        self._chunk_processor = DocumentSummaryChunkProcessor(
            ollama_llm_facade=self._ollama_llm_facade,
            document_summary_service_settings=self._settings,
            document_summary_prompt_builder=self._prompt_builder,
            ollama_llm_invoker=self._llm_invoker
        )

        logger.info("DocumentSummaryService initialized successfully")

    async def execute_document_summary(
            self,
            document_summary_request: DocumentSummaryRequest,
            user: AuthenticationResponse,
            authorization: Optional[str] = None
    ) -> DocumentSummaryResponse:
        logger.info(
            "Document summary execution initiated",
            extra={"user_id": user.id, "document_id": document_summary_request.document_id}
        )

        try:
            self._request_validator.validate_request(document_summary_request)

            context_fragments = await self._retrieve_context_fragments(
                document_id=document_summary_request.document_id,
                authorization=authorization
            )

            if not context_fragments:
                logger.warning(
                    "No fragments found for document",
                    extra={
                        "document_id": document_summary_request.document_id,
                        "user_id": user.id
                    }
                )
                return DocumentSummaryResponse(
                    summary="No fragments found to generate the summary."
                )

            summary = await self._generate_summary(context_fragments=context_fragments)

            logger.info(
                "Document summary execution completed",
                extra={"user_id": user.id, "document_id": document_summary_request.document_id}
            )
            return DocumentSummaryResponse(summary=summary)

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during document summary execution",
                extra={"user_id": user.id, "error_type": type(e).__name__}
            )
            raise DocumentSummaryServiceException(
                "Unexpected error while processing the document summary"
            ) from e

    async def _retrieve_context_fragments(
            self,
            document_id: int,
            authorization: Optional[str],
    ) -> List[str]:
        logger.debug(
            "Retrieving context fragments for document",
            extra={"document_id": document_id}
        )

        try:
            fragments = await self._document_context_provider.retrieve_context_fragments_by_document(
                document_id=document_id,
                authorization=authorization
            )

            logger.debug(
                "Context fragments retrieved",
                extra={"document_id": document_id, "fragment_count": len(fragments)}
            )
            return fragments

        except DocumentSummaryServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to retrieve context fragments",
                extra={"document_id": document_id, "error_type": type(e).__name__}
            )
            raise DocumentSummaryServiceException(
                "Error retrieving context fragments from the document service"
            ) from e

    async def _generate_summary(self, context_fragments: List[str]) -> str:
        strategy = self._settings.select_strategy(len(context_fragments))

        logger.debug(
            "Generating summary",
            extra={"strategy": strategy.value, "fragment_count": len(context_fragments)}
        )

        try:
            if strategy == SummarizationStrategy.map_reduce:
                summary = await self._summarize_map_reduce(context_fragments)
            else:
                summary = await self._summarize_direct(context_fragments)

        except DocumentSummaryServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to generate summary",
                extra={"error_type": type(e).__name__}
            )
            raise DocumentSummaryServiceException(
                "Error generating the document summary"
            ) from e

        if not summary or not summary.strip():
            logger.warning("LLM returned empty summary")
            raise DocumentSummaryServiceException("The model did not generate a valid summary")

        logger.debug("Summary generated successfully")
        return summary.strip()

    async def _summarize_direct(self, fragments: List[str]) -> str:
        logger.debug("Executing DIRECT summarization")

        llm = await self._ollama_llm_facade.get_llm_base()
        llm_input = self._prompt_builder.build_summarization_messages(
            system_prompt=self._settings.system_prompt,
            fragments=fragments
        )
        return await self._llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)

    async def _summarize_map_reduce(self, fragments: List[str]) -> str:
        logger.debug("Executing MAP_REDUCE summarization")

        chunks = self._chunk_processor.create_chunks(
            fragments=fragments,
            chunk_size=self._settings.chunk_size
        )

        partial_summaries = await self._chunk_processor.process_chunks(chunks)

        if len(partial_summaries) == 1:
            logger.debug("Single partial summary produced — skipping reduction step")
            return partial_summaries[0]

        return await self._reduce_summaries(partial_summaries)

    async def _reduce_summaries(self, partial_summaries: List[str]) -> str:
        logger.debug(
            "Reducing partial summaries",
            extra={"partial_summary_count": len(partial_summaries)}
        )

        llm = await self._ollama_llm_facade.get_llm_base()
        llm_input = self._prompt_builder.build_reduction_messages(
            system_prompt=self._settings.system_prompt,
            partial_summaries=partial_summaries
        )
        return await self._llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)


async def get_document_summary_service(request: Request) -> DocumentSummaryServiceInterface:
    try:
        return request.app.state.document_summary_service
    except AttributeError:
        logger.error("DocumentSummaryService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentSummaryService is not available",
        )
