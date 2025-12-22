import logging
from typing import Optional, Type
from pydantic import BaseModel, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.infrastructure.providers.context_provider import FragmentRetrievalService
from app.application.ollama_configurator.ollama_configurator import OllamaConfigurator

logger = logging.getLogger(__name__)


class DocumentSummaryToolInput(BaseModel):
    documentId: int


class DocumentSummaryTool(BaseTool):
    name: str = "document_summary_tool"
    description: str = (
        "Generates a comprehensive summary of a document by its ID. "
        "Use this tool when the user asks for a summary, overview, or wants to understand "
        "the main points of a document. The tool retrieves all document fragments and "
        "creates a structured summary."
    )
    args_schema: Type[BaseModel] = DocumentSummaryToolInput

    SYSTEM_PROMPT: str = (
        "Eres un asistente experto en crear resúmenes precisos y concisos de documentos. "
        "Tu tarea es analizar el contenido proporcionado y generar un resumen claro, "
        "estructurado y completo que capture los puntos principales sin perder información importante. "
        "El resumen debe estar en formato Markdown e incluir títulos (`#`), subtítulos (`##`), "
        "listas (`-`) y negritas (`**`) cuando sea apropiado."
    )

    _fragment_retrieval_service: FragmentRetrievalService = PrivateAttr()
    _ollama_configurator: OllamaConfigurator = PrivateAttr()
    _llm: Runnable = PrivateAttr()

    def __init__(self,
                 fragment_retrieval_service: FragmentRetrievalService,
                 ollama_configurator: OllamaConfigurator,
                 **kwargs):
        super().__init__(**kwargs)
        self._fragment_retrieval_service = fragment_retrieval_service
        self._ollama_configurator = ollama_configurator
        self._llm = self._ollama_configurator.get_llm_base()
        logger.debug("DocumentSummaryTool initialized")

    def _run(self,
             documentId: int,
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        raise NotImplementedError("DocumentSummaryTool does not support synchronous execution.")

    async def _arun(self,
                    documentId: int,
                    run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        logger.debug(f"Executing DocumentSummaryTool for document ID: {documentId}")

        try:
            # Obtener fragmentos del documento
            fragments = await self._fragment_retrieval_service.get_fragments_by_document_id(
                document_id=documentId
            )

            if not fragments:
                logger.info(f"No fragments found for document ID: {documentId}")
                return f"No se encontraron fragmentos para el documento con ID {documentId}."

            # Construir el prompt para el resumen
            fragments_joined = "\n\n---\n\n".join(fragments)
            prompt = (
                "Analiza el siguiente contenido de un documento y genera un resumen completo, "
                "estructurado y claro que capture los puntos principales y la información más importante.\n\n"
                f"Contenido del documento:\n\n{fragments_joined}\n\n"
                "Resumen:"
            )

            llm_input = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]

            # Invocar el LLM
            result = await self._llm.ainvoke(llm_input)

            # Extraer el resumen
            if hasattr(result, 'content'):
                summary = result.content if isinstance(result.content, str) else str(result.content)
            else:
                summary = str(result)

            logger.info(f"Summary generated successfully for document ID: {documentId}")
            return summary

        except Exception as e:
            logger.error(f"Error executing DocumentSummaryTool: {e}", exc_info=True)
            return f"Ocurrió un error al generar el resumen del documento: {str(e)}"
