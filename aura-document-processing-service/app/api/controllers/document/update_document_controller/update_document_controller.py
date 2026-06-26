from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.api.controllers.document.update_document_controller.interfaces.update_document_controller_interface import (
    UpdateDocumentControllerInterface,
)
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.document.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.document.update_document.update_document_request import UpdateDocumentRequest
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import get_update_document_service


class UpdateDocumentController(UpdateDocumentControllerInterface):
    async def update_document_manage(
            self,
            document_id: int,
            update_document_request: UpdateDocumentRequest,
            update_document_service: UpdateDocumentServiceInterface = Depends(get_update_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> DocumentResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_UPDATE_MANAGE}),
        )

        return await update_document_service.update_document_manage(
            document_id=document_id,
            update_document_request=update_document_request,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )


router = APIRouter()
update_document_controller = UpdateDocumentController()

_error = default_error_responses(
    include_400=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Documento actualizado",
        "model": DocumentResponse,
    },
    **_error,
}

router.add_api_route(
    "/manage/document/{document_id}",
    update_document_controller.update_document_manage,
    methods=["PATCH"],
    response_model=DocumentResponse,
    operation_id="updateDocumentManage",
    summary="Actualizar el título de un documento (manage)",
    description=(
        "Actualiza el título (nombre) de cualquier documento sin volver a subir el "
        "archivo y sin restricción de pertenencia al chat. La descripción y la categoría "
        "se generan por post-procesamiento y no son editables manualmente. "
        "Requiere permiso de administración."
    ),
    responses=_response,
)
