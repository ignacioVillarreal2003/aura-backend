import logging
import asyncio
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.exceptions.app_exceptions import ValidationError
from app.application.exceptions.context_provider_exception import ContextRetrievalByDocumentError
from app.application.exceptions.document_summary_service_exceptions import DocumentSummaryServiceError
from app.application.exceptions.ollama_configurator_exceptions import LLMInvocationError
from app.application.llm_configurator.interfaces.llm_configurator_interface import LLMConfiguratorInterface
from app.domain.dtos.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary_response import DocumentSummaryResponse
from app.infrastructure.providers.interfaces.context_provider_interface import ContextProviderInterface

logger = logging.getLogger(__name__)


class DocumentSummaryService:
    LARGE_DOCUMENT_THRESHOLD: int = 5
    CHUNK_SIZE: int = 5
    MAX_CONCURRENT_CHUNKS: int = 3
    MAX_RETRY_ATTEMPTS: int = 3

    SYSTEM_PROMPT: str = (
        "Eres un asistente experto en crear resúmenes precisos y concisos de documentos. "
        "Tu tarea es analizar el contenido proporcionado y generar un resumen claro, "
        "estructurado y completo que capture los puntos principales sin perder información importante. "
        "El resumen debe estar en formato Markdown e incluir títulos (`#`), subtítulos (`##`), "
        "listas (`-`) y negritas (`**`) cuando sea apropiado."
    )

    def __init__(self,
                 llm_configurator: LLMConfiguratorInterface,
                 context_provider: ContextProviderInterface) -> None:
        self._llm_configurator = llm_configurator
        self._context_provider = context_provider

        self._llm: Runnable = self._llm_configurator.get_llm_base()

        logger.debug("DocumentSummaryService initialized")

    async def execute_document_summary(self,
                                       document_summary_request: DocumentSummaryRequest) -> DocumentSummaryResponse:
        self._validate_request(document_summary_request)

        logger.info(
            "Executing document summary",
            extra={
                "document_id": document_summary_request.document_id
            }
        )

        try:
            fragments = await self._context_provider.retrieve_fragments_by_document(
                document_id=document_summary_request.document_id
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

            logger.info(
                "Retrieved fragments for summary",
                extra={
                    "document_id": document_summary_request.document_id
                }
            )

            if len(fragments) > self.LARGE_DOCUMENT_THRESHOLD:
                summary = await self._summarize_large_document(fragments)
            else:
                summary = await self._summarize_direct(fragments)

            logger.info(
                "Document summary executed successfully",
                extra={
                    "document_id": document_summary_request.document_id
                }
            )

            return DocumentSummaryResponse(summary=summary)

        except (ValidationError,
                ContextRetrievalByDocumentError,
                LLMInvocationError,
                DocumentSummaryServiceError):
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

    def _validate_request(self,
                          request: DocumentSummaryRequest) -> None:
        if request.document_id <= 0:
            raise ValidationError(
                "Document ID must be a positive integer",
                status_code=400
            )

    async def _summarize_direct(self,
                                fragments: List[str]) -> str:
        logger.debug("Using direct summarization strategy")

        llm_input = self._build_llm_input(fragments)

        result = await self._llm_configurator.call_llm_text(
            llm=self._llm,
            llm_input=llm_input
        )

        return result

    async def _summarize_large_document(self,
                                        fragments: List[str]) -> str:
        logger.debug("Using map-reduce summarization strategy for large document")

        chunks = [
            fragments[i:i + self.CHUNK_SIZE]
            for i in range(0, len(fragments), self.CHUNK_SIZE)
        ]

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_CHUNKS)

        async def summarize_chunk(chunk: List[str]) -> str:
            async with semaphore:
                for attempt in range(self.MAX_RETRY_ATTEMPTS):
                    try:
                        llm_input = self._build_llm_input(chunk)
                        result = await self._llm_configurator.call_llm_text(
                            llm=self._llm,
                            llm_input=llm_input
                        )
                        return result
                    except Exception as e:
                        if attempt == self.MAX_RETRY_ATTEMPTS - 1:
                            logger.error(
                                f"Failed to summarize chunk after {self.MAX_RETRY_ATTEMPTS} attempts",
                                extra={"error": str(e)}
                            )
                            return f"[Error al resumir fragmento: {str(e)[:100]}]"
                        await asyncio.sleep(1)
                return "[Error desconocido]"

        partial_summaries_results = await asyncio.gather(
            *[summarize_chunk(chunk) for chunk in chunks],
            return_exceptions=True
        )

        successful_summaries: List[str] = []
        for i, summary in enumerate(partial_summaries_results):
            if isinstance(summary, Exception):
                logger.warning(
                    f"Error summarizing chunk {i}",
                    extra={"error": str(summary)}
                )
            elif isinstance(summary, str):
                successful_summaries.append(summary)

        if not successful_summaries:
            raise DocumentSummaryServiceError("No partial summary could be generated")

        if len(successful_summaries) == 1:
            return successful_summaries[0]

        final_summary = await self._reduce_summaries(successful_summaries)
        return final_summary

    async def _reduce_summaries(self,
                                partial_summaries: List[str]) -> str:
        logger.debug("Reducing partial summaries into final summary")

        joined_summaries = "\n\n---\n\n".join(partial_summaries)

        prompt = (
            "A continuación tienes múltiples resúmenes parciales de un documento más grande. "
            "Fusiona todos en un único resumen final, coherente, conciso y sin repeticiones. "
            "Mantén la estructura y los puntos principales de cada sección.\n\n"
            f"Resúmenes parciales:\n\n{joined_summaries}\n\n"
            "Resumen final:"
        )

        llm_input = [
            self._build_system_message(),
            HumanMessage(content=prompt)
        ]

        result = await self._llm_configurator.call_llm_text(
            llm=self._llm,
            llm_input=llm_input
        )
        return result

    def _build_llm_input(self,
                         fragments: List[str]) -> List[BaseMessage]:
        fragments_joined = "\n\n---\n\n".join(fragments)

        prompt = (
            "Analiza el siguiente contenido de un documento y genera un resumen completo, "
            "estructurado y claro que capture los puntos principales y la información más importante.\n\n"
            f"Contenido del documento:\n\n{fragments_joined}\n\n"
            "Resumen:"
        )

        return [
            self._build_system_message(),
            HumanMessage(content=prompt)
        ]

    def _build_system_message(self) -> SystemMessage:
        return SystemMessage(
            content=self.SYSTEM_PROMPT
        )
