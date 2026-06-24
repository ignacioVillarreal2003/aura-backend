from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.api.controllers.document.document_search_controller.interfaces.document_search_controller_interface import (
    DocumentSearchControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.document.document_search_service.interfaces.document_search_service_interface import (
    DocumentSearchServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_search.document_search_request import DocumentSearchRequest
from app.domain.dtos.document.document_search.document_search_response import DocumentSearchListResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import (
    get_document_search_service,
)


class DocumentSearchController(DocumentSearchControllerInterface):
    async def search_documents_by_content(
            self,
            document_search_request: DocumentSearchRequest,
            document_search_service: DocumentSearchServiceInterface = Depends(get_document_search_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> DocumentSearchListResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_SEARCH}),
        )

        return await document_search_service.search_documents_by_content(
            document_search_request=document_search_request,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )


router = APIRouter()
document_search_controller = DocumentSearchController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Documentos más similares al contenido buscado",
        "model": DocumentSearchListResponse,
    },
    **_error,
}

router.add_api_route(
    "/by-content",
    document_search_controller.search_documents_by_content,
    methods=["POST"],
    response_model=DocumentSearchListResponse,
    operation_id="searchDocumentsByContent",
    summary="Buscar documentos por contenido",
    description=(
        "Busca los fragmentos más relevantes a la consulta y devuelve los documentos "
        "a los que pertenecen, ordenados por relevancia y paginados. Admite dos modos: "
        "`vector` (similitud semántica por embeddings, coseno) y `bm25` (relevancia "
        "léxica por palabras clave). Solo considera documentos accesibles para el usuario."
    ),
    responses=_response,
)
