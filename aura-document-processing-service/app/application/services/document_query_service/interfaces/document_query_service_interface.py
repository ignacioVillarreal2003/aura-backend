from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.document_query_controller.context_fragment_response import ContextFragmentListResponse
from app.domain.dtos.document_query_controller.document_response import (
    DocumentResponse,
    DocumentListResponse
)
from app.domain.dtos.document_query_controller.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_query_controller.question_context_fragments_request import QuestionContextFragmentsRequest
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentQueryServiceInterface(ABC):
    @abstractmethod
    async def get_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentResponse:
        pass

    @abstractmethod
    async def get_documents(
            self,
            database_session: AsyncSession,
            user: AuthenticationResponse,
            page: Optional[int] = None,
            size: Optional[int] = None
    ) -> DocumentListResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            database_session: AsyncSession
    ) -> ContextFragmentListResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            database_session: AsyncSession
    ) -> ContextFragmentListResponse:
        pass
