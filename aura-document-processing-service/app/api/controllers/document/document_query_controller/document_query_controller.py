from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.api.controllers.document.document_query_controller.interfaces.document_query_controller_interface import (
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
from app.domain.dtos.document.document_query.document_status_response import DocumentStatusResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import get_document_query_service


class DocumentQueryController(DocumentQueryControllerInterface):
    async def get_document_manage(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> DocumentResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_QUERY_MANAGE}),
        )

        return await document_query_service.get_document_manage(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )

    async def get_document_status_manage(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> DocumentStatusResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_QUERY_MANAGE}),
        )

        return await document_query_service.get_document_status_manage(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )

    async def get_document_status(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> DocumentStatusResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_QUERY}),
        )

        return await document_query_service.get_document_status(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )

    async def get_documents_manage(
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
            required_permissions=frozenset({Permissions.DOCUMENT_QUERY_MANAGE}),
        )

        return await document_query_service.get_documents_manage(
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
            required_permissions=frozenset({Permissions.DOCUMENT_QUERY}),
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
_response_status = {
    200: {
        "description": "Estado de procesamiento del documento",
        "model": DocumentStatusResponse,
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
    "/manage/document/{document_id}",
    document_query_controller.get_document_manage,
    methods=["GET"],
    response_model=DocumentResponse,
    operation_id="getDocumentByIdManage",
    summary="Obtener documento por ID (manage)",
    description="Devuelve cualquier documento por su ID sin restricción de pertenencia al chat. Requiere permiso de administración.",
    responses=_response_one,
)
router.add_api_route(
    "/manage/document/{document_id}/status",
    document_query_controller.get_document_status_manage,
    methods=["GET"],
    response_model=DocumentStatusResponse,
    operation_id="getDocumentStatusManage",
    summary="Obtener estado de procesamiento de un documento (manage)",
    description=(
        "Devuelve una proyección liviana del estado de cualquier documento (status, "
        "enrichment_status, graph_status y marcas de procesamiento), pensada para "
        "hacer polling del pipeline asíncrono de ingesta sin transferir el documento completo. "
        "Requiere permiso de administración."
    ),
    responses=_response_status,
)
router.add_api_route(
    "/document/{document_id}/status",
    document_query_controller.get_document_status,
    methods=["GET"],
    response_model=DocumentStatusResponse,
    operation_id="getDocumentStatus",
    summary="Obtener estado de procesamiento de un documento",
    description=(
        "Devuelve una proyección liviana del estado del documento (status, "
        "enrichment_status, graph_status y marcas de procesamiento), aplicando permisos "
        "de acceso del usuario. Pensada para hacer polling del pipeline asíncrono de "
        "ingesta sin transferir el documento completo."
    ),
    responses=_response_status,
)
router.add_api_route(
    "/manage/documents",
    document_query_controller.get_documents_manage,
    methods=["GET"],
    response_model=DocumentListResponse,
    operation_id="listDocumentsManage",
    summary="Listar documentos (manage)",
    description=(
        "Devuelve documentos con filtros opcionales, sin restricción de pertenencia al chat. "
        "La paginación es opcional: si se omiten 'page' y 'size' se devuelven todos los "
        "documentos que coinciden (hasta un máximo de seguridad); si se envía alguno, se pagina. "
        "Requiere permiso de administración."
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
