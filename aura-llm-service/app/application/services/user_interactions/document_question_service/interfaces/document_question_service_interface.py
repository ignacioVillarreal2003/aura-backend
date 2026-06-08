from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.user_interactions.document_question.document_question_response import DocumentQuestionResponse
from app.domain.dtos.user_interactions.document_question.document_question_stream_events import (
    DocumentQuestionStreamEvent,
)


class DocumentQuestionServiceInterface(ABC):
    @abstractmethod
    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentQuestionResponse:
        pass

    @abstractmethod
    async def execute_document_question_stream(
            self,
            document_question_request: DocumentQuestionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[DocumentQuestionStreamEvent]:
        ...
