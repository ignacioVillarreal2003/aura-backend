import logging
from typing import Optional, Type
from pydantic import BaseModel, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun
)

from app.application.services.document_summary_service import DocumentSummaryService
from app.domain.dtos.document_summary_request import DocumentSummaryRequest

logger = logging.getLogger(__name__)


class DocumentSummaryToolInput(BaseModel):
    document_id: int


class DocumentSummaryTool(BaseTool):
    name: str = "document_summary_tool"
    description: str = (
        "Generates a comprehensive summary of a document by its ID. "
        "Use this tool when the user asks for a summary, overview, or wants to understand "
        "the main points of a document. The tool retrieves all document fragments and "
        "creates a structured summary."
    )
    args_schema: Type[BaseModel] = DocumentSummaryToolInput

    _document_summary_service: DocumentSummaryService = PrivateAttr()

    def __init__(self,
                 document_summary_service: DocumentSummaryService,
                 **kwargs):
        super().__init__(**kwargs)
        self._document_summary_service = document_summary_service

    def _run(self,
             document_id: int,
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        raise NotImplementedError("DocumentSummaryTool does not support synchronous execution.")

    async def _arun(self,
                    document_id: int,
                    run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        logger.debug(
            "Executing DocumentSummaryTool",
            extra={
                "document_id": document_id
            }
        )

        try:
            request = DocumentSummaryRequest(
                document_id=document_id
            )
            response = await self._document_summary_service.execute_document_summary(request)

            logger.info(
                "Summary generated successfully",
                extra={
                    "document_id": document_id
                }
            )
            return response.summary

        except Exception as e:
            logger.error(
                f"Error executing DocumentSummaryTool: {e}",
                exc_info=True
            )
            return f"Ocurrió un error al generar el resumen del documento: {str(e)}"
