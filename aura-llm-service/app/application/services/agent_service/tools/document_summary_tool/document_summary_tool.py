import logging
from typing import Optional, Type
from pydantic import BaseModel, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun

from app.application.services.agent_service.tools.document_summary_tool.document_summary_tool_input import (
    DocumentSummaryToolInput
)
from app.application.services.document_summary_service.document_summary_service import DocumentSummaryService
from app.application.services.document_summary_service.interfaces.document_summary_service_interface import \
    DocumentSummaryServiceInterface
from app.domain.dtos.document_summary_request import DocumentSummaryRequest

logger = logging.getLogger(__name__)


class DocumentSummaryTool(BaseTool):
    name: str = "document_summary_tool"
    description: str = (
        "Generates a comprehensive summary of a document by its ID. "
        "Use this tool when the user asks for a summary, overview, or wants to understand "
        "the main points of a document. The tool retrieves all document fragments and "
        "creates a structured summary using adaptive strategies (DIRECT for small documents, "
        "MAP_REDUCE for large ones).\n\n"
        "Input: document_id (integer)\n"
        "Output: Structured summary in Markdown format"
    )
    args_schema: Type[BaseModel] = DocumentSummaryToolInput

    _document_summary_service: DocumentSummaryServiceInterface = PrivateAttr()

    def __init__(
            self,
            document_summary_service: DocumentSummaryServiceInterface,
            **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._document_summary_service = document_summary_service

        logger.info(
            "DocumentSummaryTool initialized",
            extra={
                "tool_name": self.name
            }
        )

    def _run(
            self,
            document_id: int,
            run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        raise NotImplementedError("DocumentSummaryTool solo soporta ejecución asíncrona. Use _arun() en su lugar.")

    async def _arun(
            self,
            document_id: int,
            run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        logger.info(
            "DocumentSummaryTool invoked",
            extra={
                "document_id": document_id
            }
        )

        try:
            document_summary_request = DocumentSummaryRequest(
                document_id=document_id
            )

            document_summary_response = await self._document_summary_service.execute_document_summary(
                document_summary_request=document_summary_request
            )

            if not document_summary_response.summary or not document_summary_response.summary.strip():
                logger.warning(
                    "Service returned empty summary",
                    extra={
                        "document_id": document_id
                    }
                )
                return "No se encontraron fragmentos para generar el resumen del documento."

            logger.info(
                "Summary generated successfully",
                extra={
                    "document_id": document_id,
                    "summary": document_summary_response.summary
                }
            )

            return document_summary_response.summary

        except Exception as e:
            logger.error(
                "Error executing DocumentSummaryTool",
                extra={
                    "document_id": document_id,
                    "error_type": type(e).__name__,
                    "error": str(e)
                },
                exc_info=True
            )
            return (
                "Ocurrió un error al procesar la solicitud. "
                "No fue posible generar una respuesta basada en los documentos disponibles."
            )
