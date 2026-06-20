from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.api.controllers.fragment.fragment_query_controller.fragment_query_controller_interface import (
    FragmentQueryControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.fragment.fragment_query_service.interfaces.fragment_query_service_interface import (
    FragmentQueryServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.fragment.fragment_query.documents_context_fragments_request import (
    DocumentsContextFragmentsRequest,
)
from app.domain.dtos.fragment.fragment_query.fragment_list_response import FragmentListResponse
from app.domain.dtos.fragment.fragment_query.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import (
    get_fragment_query_service,
)


class FragmentQueryController(FragmentQueryControllerInterface):
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            fragment_query_service: FragmentQueryServiceInterface = Depends(get_fragment_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> FragmentListResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.FRAGMENT_QUERY}),
        )

        return await fragment_query_service.retrieve_context_fragments_by_question(
            question_context_fragments_request=question_context_fragments_request,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )

    async def retrieve_context_fragments_by_documents(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest,
            fragment_query_service: FragmentQueryServiceInterface = Depends(get_fragment_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> FragmentListResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.FRAGMENT_QUERY}),
        )

        return await fragment_query_service.retrieve_context_fragments_by_documents(
            documents_context_fragments_request=documents_context_fragments_request,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )


router = APIRouter()
fragment_query_controller = FragmentQueryController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Fragmentos de contexto",
        "model": FragmentListResponse,
    },
    **_error,
}

router.add_api_route(
    "/by-question",
    fragment_query_controller.retrieve_context_fragments_by_question,
    methods=["POST"],
    response_model=FragmentListResponse,
    operation_id="getFragmentsByQuestion",
    summary="Obtener fragmentos por pregunta",
    description="Devuelve fragmentos relevantes para una pregunta.",
    responses=_response,
)
router.add_api_route(
    "/by-documents",
    fragment_query_controller.retrieve_context_fragments_by_documents,
    methods=["POST"],
    response_model=FragmentListResponse,
    operation_id="getFragmentsByDocuments",
    summary="Obtener fragmentos por documentos",
    description="Devuelve fragmentos de contexto de los documentos enviados.",
    responses=_response,
)
