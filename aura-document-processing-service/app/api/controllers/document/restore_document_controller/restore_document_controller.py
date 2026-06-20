from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.api.controllers.document.restore_document_controller.interfaces.restore_document_controller_interface import (
    RestoreDocumentControllerInterface,
)
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.document.restore_document_service.interfaces.restore_document_service_interface import (
    RestoreDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import get_restore_document_service


class RestoreDocumentController(RestoreDocumentControllerInterface):
    async def restore_document_manage(
            self,
            document_id: int,
            restore_document_service: RestoreDocumentServiceInterface = Depends(get_restore_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> DocumentResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_RESTORE_MANAGE}),
        )

        return await restore_document_service.restore_document_manage(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )


router = APIRouter()
restore_document_controller = RestoreDocumentController()

_error = default_error_responses(
    include_400=True,
    include_409=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Documento restaurado",
        "model": DocumentResponse,
    },
    **_error,
}

router.add_api_route(
    "/manage/document/{document_id}",
    restore_document_controller.restore_document_manage,
    methods=["POST"],
    response_model=DocumentResponse,
    operation_id="restoreDocumentManage",
    summary="Restaurar documento (manage)",
    description=(
        "Restaura cualquier documento previamente eliminado de forma lógica sin restricción "
        "de pertenencia al chat, limpiando las marcas de borrado del documento y de sus "
        "fragmentos. Responde 409 si el documento no está eliminado. Requiere permiso de "
        "administración. Nota: si el purgado asíncrono del footprint externo (MinIO/Neo4j) ya "
        "se ejecutó, el archivo y el grafo no se recuperan."
    ),
    responses=_response,
)
