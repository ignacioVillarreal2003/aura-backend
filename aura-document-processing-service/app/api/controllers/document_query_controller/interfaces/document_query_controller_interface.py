from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.dtos.document_query_controller.context_fragment_response import ContextFragmentListResponse
from app.domain.dtos.document_query_controller.document_response import (
    DocumentResponse,
    DocumentListResponse
)
from app.domain.dtos.document_query_controller.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_query_controller.question_context_fragments_request import QuestionContextFragmentsRequest
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentQueryControllerInterface(ABC):
    @abstractmethod
    async def get_document(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentResponse:
        pass

    @abstractmethod
    async def get_documents(
            self,
            page: Optional[int],
            size: Optional[int],
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentListResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession
    ) -> ContextFragmentListResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession
    ) -> ContextFragmentListResponse:
        pass
