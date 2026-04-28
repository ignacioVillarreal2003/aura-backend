import logging
from typing import Optional, Type
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, PrivateAttr

from app.application.services.agent_service.tools.document_summary_tool.document_summary_tool_input import (
    DocumentSummaryToolInput
)
from app.application.authorization.permissions import Permissions
from app.application.services.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document_summary.document_summary_request import DocumentSummaryRequest

logger = logging.getLogger(__name__)


class DocumentSummaryTool(BaseTool):
    _TOOL_USER = AuthenticatedUser(
        id=0,
        email="tool@agent",
        roles=[],
        permissions=[Permissions.LLM_DOCUMENT_SUMMARY],
    )

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
    _authorization: Optional[str] = PrivateAttr(default=None)

    def __init__(
            self,
            document_summary_service: DocumentSummaryServiceInterface,
            **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._document_summary_service = document_summary_service
        logger.info("DocumentSummaryTool initialized", extra={"tool_name": self.name})

    def set_authorization(self, authorization: Optional[str]) -> None:
        self._authorization = authorization

    def _run(
            self,
            document_id: int,
            run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        raise NotImplementedError(
            "DocumentSummaryTool only supports async execution. Use _arun() instead."
        )

    async def _arun(
            self,
            document_id: int,
            run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        logger.info("DocumentSummaryTool invoked", extra={"document_id": document_id})

        try:
            response = await self._document_summary_service.execute_document_summary(
                document_summary_request=DocumentSummaryRequest(document_id=document_id),
                authenticated_user=self._TOOL_USER,
            )

            if not response.summary or not response.summary.strip():
                logger.warning(
                    "Service returned empty summary",
                    extra={"document_id": document_id}
                )
                return "No fragments found to generate the document summary."

            logger.info(
                "Summary generated successfully",
                extra={"document_id": document_id}
            )
            return response.summary

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
                "An error occurred while processing the request. "
                "It was not possible to generate a summary based on the available documents."
            )
