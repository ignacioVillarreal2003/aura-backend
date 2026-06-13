from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.api.controllers.document.document_query_controller.document_query_controller_interface import (
    DocumentQueryControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.document.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.document_type import DocumentType
from app.domain.field_limits import (
    MAX_CATEGORY_CHARS,
    MAX_DESCRIPTION_CHARS,
    MAX_DOCUMENT_QUERY_PAGE_SIZE,
    MAX_NAME_CHARS,
)
from app.domain.dtos.document.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import (
    get_document_query_service,
)

class DocumentQueryController(DocumentQueryControllerInterface):
    async def get_document(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> DocumentResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GET_DOCUMENT}),
        )

        return await document_query_service.get_document(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )

    async def get_documents(
            self,
            page: Optional[int] = Query(None, ge=1),
            size: Optional[int] = Query(None, ge=1, le=MAX_DOCUMENT_QUERY_PAGE_SIZE),
            name: Optional[str] = Query(None, max_length=MAX_NAME_CHARS),
            description: Optional[str] = Query(None, max_length=MAX_DESCRIPTION_CHARS),
            category: Optional[str] = Query(None, max_length=MAX_CATEGORY_CHARS),
            document_type: Optional[DocumentType] = Query(None),
            created_from: Optional[datetime] = Query(None),
            created_to: Optional[datetime] = Query(None),
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> DocumentListResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LIST_DOCUMENTS}),
        )

        return await document_query_service.get_documents(
            database_session=database_session,
            authenticated_user=authenticated_user,
            page=page,
            size=size,
            name=name,
            description=description,
            category=category,
            document_type=document_type,
            created_from=created_from,
            created_to=created_to,
        )

    async def get_documents_by_chat(
            self,
            chat_id: int,
            page: Optional[int] = Query(None, ge=1),
            size: Optional[int] = Query(None, ge=1, le=MAX_DOCUMENT_QUERY_PAGE_SIZE),
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> DocumentListResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LIST_DOCUMENTS_BY_CHAT}),
        )

        return await document_query_service.get_documents_by_chat(
            chat_id=chat_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
            page=page,
            size=size,
        )

router = APIRouter()
document_query_controller = DocumentQueryController()

_error = default_error_responses(
    include_400=True,
    include_503=True,
)
_response_one = {
    200: {
        "description": "Documento",
        "model": DocumentResponse,
    },
    **_error,
}
_response_list = {
    200: {
        "description": "Listado de documentos",
        "model": DocumentListResponse,
    },
    **_error,
}

router.add_api_route(
    "/document/{document_id}",
    document_query_controller.get_document,
    methods=["GET"],
    response_model=DocumentResponse,
    operation_id="getDocumentById",
    summary="Obtener documento por ID",
    description="Devuelve un documento por su ID, aplicando permisos de acceso.",
    responses=_response_one,
)
router.add_api_route(
    "/documents",
    document_query_controller.get_documents,
    methods=["GET"],
    response_model=DocumentListResponse,
    operation_id="listDocuments",
    summary="Listar documentos",
    description=(
        "Devuelve documentos con filtros opcionales. La paginación es opcional: "
        "si se omiten 'page' y 'size' se devuelven todos los documentos que coinciden "
        "(hasta un máximo de seguridad); si se envía alguno, se pagina."
    ),
    responses=_response_list,
)
router.add_api_route(
    "/documents/chat/{chat_id}",
    document_query_controller.get_documents_by_chat,
    methods=["GET"],
    response_model=DocumentListResponse,
    operation_id="listDocumentsByChat",
    summary="Listar documentos por chat",
    description=(
        "Devuelve los documentos asociados a un chat. La paginación es opcional: "
        "si se omiten 'page' y 'size' se devuelven todos los documentos del chat "
        "(hasta un máximo de seguridad); si se envía alguno, se pagina."
    ),
    responses=_response_list,
)
