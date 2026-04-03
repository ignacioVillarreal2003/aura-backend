import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.api.controllers.fragment_controllers.fragment_query_controller.interfaces.fragment_query_controller_interface import (
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
from app.domain.authentication.authenticated_user import AuthenticatedUser
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
        logger.info(
            "Handling retrieve fragments by question request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        fragment_list_response = await fragment_query_service.retrieve_context_fragments_by_question(
            question_context_fragments_request=question_context_fragments_request,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Retrieve fragments by question completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return fragment_list_response

    async def retrieve_context_fragments_by_documents(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest,
            fragment_query_service: FragmentQueryServiceInterface = Depends(get_fragment_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> FragmentListResponse:
        logger.info(
            "Handling retrieve fragments by documents request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        fragment_list_response = await fragment_query_service.retrieve_context_fragments_by_documents(
            documents_context_fragments_request=documents_context_fragments_request,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Retrieve fragments by documents completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return fragment_list_response


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
