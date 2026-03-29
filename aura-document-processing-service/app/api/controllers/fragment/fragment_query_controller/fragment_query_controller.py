import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.api.controllers.controller_logging import log_controller
from app.api.controllers.fragment.fragment_query_controller.interfaces.fragment_query_controller_interface import (
    FragmentQueryControllerInterface
)
from app.application.services.fragment.fragment_query_service.fragment_query_service import get_fragment_query_service
from app.application.services.fragment.fragment_query_service.interfaces.fragment_query_service_interface import (
    FragmentQueryServiceInterface
)
from app.domain.dtos.fragment.fragment_query_controller.documents_context_fragments_request import (
    DocumentsContextFragmentsRequest
)
from app.domain.dtos.fragment.fragment_query_controller.fragment_list_response import FragmentListResponse
from app.domain.dtos.fragment.fragment_query_controller.question_context_fragments_request import (
    QuestionContextFragmentsRequest
)
from app.domain.models.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session

logger = logging.getLogger(__name__)


class FragmentQueryController(FragmentQueryControllerInterface):
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            fragment_query_service: FragmentQueryServiceInterface = Depends(get_fragment_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> FragmentListResponse:
        log_controller(
            logger,
            operation="retrieve_context_fragments_by_query",
            phase="start",
            user_id=authenticated_user.id,
            question_length=len(question_context_fragments_request.query or ""),
        )

        context_fragment_list_response = await fragment_query_service.retrieve_context_fragments_by_question(
            question_context_fragments_request=question_context_fragments_request,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        log_controller(
            logger,
            operation="retrieve_context_fragments_by_question",
            phase="success",
            user_id=authenticated_user.id,
            fragment_count=len(context_fragment_list_response.context_fragments),
        )

        return context_fragment_list_response

    async def retrieve_context_fragments_by_documents(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest,
            fragment_query_service: FragmentQueryServiceInterface = Depends(get_fragment_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> FragmentListResponse:
        log_controller(
            logger,
            operation="retrieve_context_fragments_by_documents",
            phase="start",
            user_id=authenticated_user.id,
            document_ids=documents_context_fragments_request.document_ids,
        )

        context_fragment_list_response = await fragment_query_service.retrieve_context_fragments_by_documents(
            documents_context_fragments_request=documents_context_fragments_request,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        log_controller(
            logger,
            operation="retrieve_context_fragments_by_documents",
            phase="success",
            user_id=authenticated_user.id,
            document_ids=documents_context_fragments_request.document_ids,
            fragment_count=len(context_fragment_list_response.context_fragments),
        )

        return context_fragment_list_response


router = APIRouter()

fragment_query_controller = FragmentQueryController()

router.post(
    "/by-question",
    response_model=FragmentListResponse
)(fragment_query_controller.retrieve_context_fragments_by_question)

router.post(
    "/by-documents",
    response_model=FragmentListResponse
)(fragment_query_controller.retrieve_context_fragments_by_documents)
