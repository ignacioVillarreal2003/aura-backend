from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.api.controllers.document.delete_document_controller.interfaces.delete_document_controller_interface import (
    DeleteDocumentControllerInterface,
)
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.document.delete_document_service.interfaces.delete_document_service_interface import (
    DeleteDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import get_delete_document_service


class DeleteDocumentController(DeleteDocumentControllerInterface):
    async def soft_delete_document(
            self,
            document_id: int,
            delete_document_service: DeleteDocumentServiceInterface = Depends(get_delete_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> Response:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_DELETE}),
        )

        await delete_document_service.soft_delete_document(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def soft_delete_documents_by_chat(
            self,
            chat_id: int,
            delete_document_service: DeleteDocumentServiceInterface = Depends(get_delete_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> Response:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_DELETE}),
        )

        await delete_document_service.soft_delete_documents_by_chat(
            chat_id=chat_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def soft_delete_document_manage(
            self,
            document_id: int,
            delete_document_service: DeleteDocumentServiceInterface = Depends(get_delete_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> Response:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_DELETE_MANAGE}),
        )

        await delete_document_service.soft_delete_document_manage(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)


router = APIRouter()
delete_document_controller = DeleteDocumentController()

_error = default_error_responses(
    include_400=True,
    include_503=True,
)
_response = {
    204: {
        "description": "Borrado aplicado, sin cuerpo",
    },
    **_error,
}

router.add_api_route(
    "/soft/document/{document_id}",
    delete_document_controller.soft_delete_document,
    methods=["DELETE"],
    response_class=Response,
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="softDeleteDocument",
    summary="Eliminar documento (lógico)",
    description="Marca un documento como eliminado y responde 204.",
    responses=_response,
)
router.add_api_route(
    "/soft/chat/{chat_id}",
    delete_document_controller.soft_delete_documents_by_chat,
    methods=["DELETE"],
    response_class=Response,
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="softDeleteDocumentsByChat",
    summary="Eliminar documentos por chat",
    description="Marca como eliminados los documentos de un chat y responde 204.",
    responses=_response,
)
router.add_api_route(
    "/manage/soft/document/{document_id}",
    delete_document_controller.soft_delete_document_manage,
    methods=["DELETE"],
    response_class=Response,
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="softDeleteDocumentManage",
    summary="Eliminar documento (manage)",
    description=(
        "Marca como eliminado cualquier documento sin restricción de pertenencia al chat "
        "y responde 204. Requiere permiso de administración."
    ),
    responses=_response,
)
