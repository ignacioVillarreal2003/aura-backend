import logging
from typing import Optional, Type
from pydantic import BaseModel, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun

from app.application.services.agent_service.tools.document_question_tool.document_question_tool_input import (
    DocumentQuestionToolInput
)
from app.application.services.document_question_service.interfaces.document_question_service_interface import \
    DocumentQuestionServiceInterface
from app.domain.dtos.document_question_request import DocumentQuestionRequest

logger = logging.getLogger(__name__)


class DocumentQuestionTool(BaseTool):
    name: str = "document_question_tool"
    description: str = (
        "Retrieves relevant information from document knowledge base and answers questions. "
        "Use this when you need to access specific information from uploaded documents or "
        "when answering questions that require domain-specific knowledge. "
        "Returns both the relevant context and a generated answer."
    )
    args_schema: Type[BaseModel] = DocumentQuestionToolInput

    _document_question_service: DocumentQuestionServiceInterface = PrivateAttr()

    def __init__(self,
                 document_question_service: DocumentQuestionServiceInterface,
                 **kwargs):
        super().__init__(**kwargs)
        self._document_question_service = document_question_service

        logger.info(
            "DocumentQuestionTool initialized",
            extra={
                "tool_name": self.name
            }
        )

    def _run(self,
             question: str,
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        raise NotImplementedError("DocumentQuestionTool solo soporta ejecución asíncrona. Use _arun() en su lugar.")

    async def _arun(self,
                    question: str,
                    run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        logger.info(
            "DocumentQuestionTool invoked",
            extra={
                "question": question
            }
        )

        try:
            request = DocumentQuestionRequest(
                question=question
            )

            response = await self._document_question_service.execute_document_question(request)

            if not response.answer or not response.answer.strip():
                logger.warning(
                    "Service returned empty answer",
                    extra={
                        "question": question
                    }
                )
                return "No se encontraron fragmentos para generar el la pregunta."

            logger.info(
                "Question generated successfully",
                extra={
                    "question": question,
                    "answer": response.answer
                }
            )

            return response.answer

        except Exception as e:
            logger.error(
                "Error executing DocumentQuestionTool",
                extra={
                    "question": question,
                    "error_type": type(e).__name__,
                    "error": str(e)
                },
                exc_info=True
            )
            return (
                "Ocurrió un error al procesar la solicitud. "
                "No fue posible generar una respuesta basada en los documentos disponibles."
            )
