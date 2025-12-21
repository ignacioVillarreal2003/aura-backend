import logging
import asyncio
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.exceptions.summary_service_exceptions import (
    SummaryServiceError,
    DocumentFragmentsRetrievalError,
    SummaryGenerationError
)
from app.application.exceptions.fragment_retrieval_service_exception import FragmentRetrievalServiceError
from app.application.ollama_configurator.ollama_configurator import OllamaConfigurator
from app.application.services.fragment_retrieval_service import FragmentRetrievalService
from app.domain.dtos.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary_response import DocumentSummaryResponse

logger = logging.getLogger(__name__)


class DocumentSummaryService:
    # Constantes de configuración
    LARGE_DOCUMENT_THRESHOLD: int = 5  # Número de fragmentos para considerar documento grande
    CHUNK_SIZE: int = 5  # Tamaño de chunks para procesamiento paralelo
    MAX_CONCURRENT_CHUNKS: int = 3  # Máximo de chunks procesados en paralelo
    MAX_RETRY_ATTEMPTS: int = 3  # Intentos máximos para resumir un chunk

    SYSTEM_PROMPT: str = (
        "Eres un asistente experto en crear resúmenes precisos y concisos de documentos. "
        "Tu tarea es analizar el contenido proporcionado y generar un resumen claro, "
        "estructurado y completo que capture los puntos principales sin perder información importante. "
        "El resumen debe estar en formato Markdown e incluir títulos (`#`), subtítulos (`##`), "
        "listas (`-`) y negritas (`**`) cuando sea apropiado."
    )

    def __init__(self,
                 ollama_configurator: OllamaConfigurator,
                 fragment_retrieval_service: FragmentRetrievalService) -> None:
        self.ollama_configurator = ollama_configurator
        self.fragment_retrieval_service = fragment_retrieval_service
        self.llm: Runnable = self.ollama_configurator.get_llm_base()

    async def execute_document_summary(self,
                       request: DocumentSummaryRequest) -> DocumentSummaryResponse:
        logger.info(f"Starting summary generation for document ID: {request.documentId}")

        try:
            # Obtener fragmentos del documento
            fragments = await self.fragment_retrieval_service.get_fragments_by_document_id(
                document_id=request.documentId
            )

            if not fragments:
                logger.warning(f"No fragments found for document ID: {request.documentId}")
                return DocumentSummaryResponse(
                    summary="No se encontraron fragmentos para generar el resumen."
                )

            logger.info(f"Retrieved {len(fragments)} fragments for document ID: {request.documentId}")

            # Si hay muchos fragmentos, usar estrategia de resumen por chunks
            if len(fragments) > self.LARGE_DOCUMENT_THRESHOLD:
                summary = await self._summarize_large_document(fragments)
            else:
                summary = await self._summarize_direct(fragments)

            logger.info(f"Summary generated successfully for document ID: {request.documentId}")
            return DocumentSummaryResponse(summary=summary)

        except FragmentRetrievalServiceError as e:
            logger.error(f"Error retrieving fragments: {e}")
            raise DocumentFragmentsRetrievalError(
                f"Error al recuperar los fragmentos del documento: {str(e)}"
            ) from e
        except Exception as e:
            logger.exception("Unexpected error during summary generation")
            raise SummaryGenerationError(
                f"Error inesperado al generar el resumen: {str(e)}"
            ) from e

    async def _summarize_direct(self,
                                fragments: List[str]) -> str:
        """Resume directamente todos los fragmentos en una sola llamada al LLM."""
        logger.debug("Using direct summarization strategy")

        llm_input = self._build_llm_input(fragments)
        result = await self._invoke_llm(llm_input)
        summary = self._extract_summary(result)

        return summary

    async def _summarize_large_document(self,
                                       fragments: List[str]) -> str:
        """Resume documentos grandes usando estrategia de map-reduce."""
        logger.debug("Using map-reduce summarization strategy for large document")

        # Dividir fragmentos en chunks para procesamiento paralelo
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
                        result = await self._invoke_llm(llm_input)
                        return self._extract_summary(result)
                    except Exception as e:
                        if attempt == self.MAX_RETRY_ATTEMPTS - 1:
                            logger.error(
                                f"Failed to summarize chunk after {self.MAX_RETRY_ATTEMPTS} attempts: {e}"
                            )
                            return f"[Error al resumir fragmento: {str(e)[:100]}]"
                        await asyncio.sleep(1)

        # Resumir chunks en paralelo
        partial_summaries = await asyncio.gather(
            *[summarize_chunk(chunk) for chunk in chunks],
            return_exceptions=True
        )

        # Filtrar errores y mantener solo resúmenes exitosos
        successful_summaries: List[str] = []
        for i, summary in enumerate(partial_summaries):
            if isinstance(summary, Exception):
                logger.warning(f"Error summarizing chunk {i}: {summary}")
            elif isinstance(summary, str):
                successful_summaries.append(summary)

        if not successful_summaries:
            raise SummaryGenerationError("No se pudo generar ningún resumen parcial")

        # Si solo hay un resumen parcial, retornarlo directamente
        if len(successful_summaries) == 1:
            return successful_summaries[0]

        # Combinar resúmenes parciales en un resumen final
        final_summary = await self._reduce_summaries(successful_summaries)
        return final_summary

    async def _reduce_summaries(self,
                                partial_summaries: List[str]) -> str:
        """Combina múltiples resúmenes parciales en un resumen final coherente."""
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
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]

        result = await self._invoke_llm(llm_input)
        return self._extract_summary(result)

    def _build_llm_input(self,
                        fragments: List[str]) -> List[BaseMessage]:
        """Construye el input para el LLM con los fragmentos del documento."""
        fragments_joined = "\n\n---\n\n".join(fragments)

        prompt = (
            "Analiza el siguiente contenido de un documento y genera un resumen completo, "
            "estructurado y claro que capture los puntos principales y la información más importante.\n\n"
            f"Contenido del documento:\n\n{fragments_joined}\n\n"
            "Resumen:"
        )

        return [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]

    async def _invoke_llm(self,
                         llm_input: List[BaseMessage]) -> BaseMessage:
        """Invoca el LLM con el input proporcionado."""
        logger.debug("Invoking LLM for summary generation")

        try:
            result: BaseMessage = await self.llm.ainvoke(llm_input)

            if not isinstance(result, BaseMessage):
                logger.error("LLM returned invalid type")
                raise SummaryGenerationError("LLM retornó un tipo inválido")

            return result

        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            raise SummaryGenerationError(f"Error al invocar el LLM: {str(e)}") from e

    def _extract_summary(self,
                        result: BaseMessage) -> str:
        """Extrae el resumen del resultado del LLM."""
        content = result.content

        if isinstance(content, str):
            return content

        logger.warning("LLM returned non-string content")
        return str(content)
