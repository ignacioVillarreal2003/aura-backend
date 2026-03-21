from abc import ABC, abstractmethod
from fastapi import Request

from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question.document_question_response import DocumentQuestionResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentQuestionControllerInterface(ABC):
    @abstractmethod
    async def execute_document_question(
            self,
            request: Request,
            document_question_request: DocumentQuestionRequest,
            document_question_service: DocumentQuestionServiceInterface,
            user: AuthenticationResponse
    ) -> DocumentQuestionResponse:
        pass
