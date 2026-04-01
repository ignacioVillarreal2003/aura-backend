import logging
from typing import Optional, Type
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, PrivateAttr

from app.application.services.general.agent_service.tools.document_question_tool.document_question_tool_input import (
    DocumentQuestionToolInput
)
from app.application.services.general.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.general.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.message import Message
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse

logger = logging.getLogger(__name__)


class DocumentQuestionTool(BaseTool):
    _TOOL_USER = AuthenticationResponse(id=0, email="tool@agent", roles=[], permissions=[])

    name: str = "document_question_tool"
    description: str = (
        "Retrieves relevant information from the document knowledge base and answers questions. "
        "Use this when you need to access specific information from uploaded documents or "
        "when answering questions that require domain-specific knowledge. "
        "Returns a generated answer grounded on the document context."
    )
    args_schema: Type[BaseModel] = DocumentQuestionToolInput

    _document_question_service: DocumentQuestionServiceInterface = PrivateAttr()
    _authorization: Optional[str] = PrivateAttr(default=None)

    def __init__(
            self,
            document_question_service: DocumentQuestionServiceInterface,
            **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._document_question_service = document_question_service
        logger.info("DocumentQuestionTool initialized", extra={"tool_name": self.name})

    def set_authorization(self, authorization: Optional[str]) -> None:
        self._authorization = authorization

    def _run(
            self,
            question: str,
            run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        raise NotImplementedError(
            "DocumentQuestionTool only supports async execution. Use _arun() instead."
        )

    async def _arun(
            self,
            question: str,
            run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        logger.info("DocumentQuestionTool invoked", extra={"question_length": len(question)})

        try:
            response = await self._document_question_service.execute_document_question(
                document_question_request=DocumentQuestionRequest(
                    messages=[
                        Message(role=MessageRole.human, content=question)
                    ]
                ),
                user=self._TOOL_USER,
                authorization=self._authorization,
            )

            if not response.answer or not response.answer.strip():
                logger.warning(
                    "Service returned empty answer",
                    extra={"question_length": len(question)}
                )
                return "No relevant information found to answer the question."

            logger.info(
                "Question answered successfully",
                extra={"question_length": len(question)}
            )
            return response.answer

        except Exception as e:
            logger.error(
                "Error executing DocumentQuestionTool",
                extra={
                    "question_length": len(question),
                    "error_type": type(e).__name__,
                    "error": str(e)
                },
                exc_info=True
            )
            return (
                "An error occurred while processing the request. "
                "It was not possible to generate an answer based on the available documents."
            )
