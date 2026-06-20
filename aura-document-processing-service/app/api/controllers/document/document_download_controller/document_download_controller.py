from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.controllers.document.document_download_controller.interfaces.download_document_controller_interface import (
    DocumentDownloadControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.document.document_download_service.interfaces.document_download_service_interface import (
    DocumentDownloadServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import get_document_download_service


class DocumentDownloadController(DocumentDownloadControllerInterface):
    async def download_document(
            self,
            document_id: int,
            document_download_service: DocumentDownloadServiceInterface = Depends(get_document_download_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_DOWNLOAD}),
        )

        content_stream, filename, mime_type = await document_download_service.download_document(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )
        return StreamingResponse(
            content=content_stream,
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
            },
        )

    async def download_document_manage(
            self,
            document_id: int,
            document_download_service: DocumentDownloadServiceInterface = Depends(get_document_download_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.DOCUMENT_DOWNLOAD_MANAGE}),
        )

        content_stream, filename, mime_type = await document_download_service.download_document_manage(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )
        return StreamingResponse(
            content=content_stream,
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
            },
        )


router = APIRouter()
document_download_controller = DocumentDownloadController()

_error = default_error_responses(
    include_404=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Fichero del documento",
        "content": {"*/*": {}},
    },
    **_error,
}

router.add_api_route(
    "/document/{document_id}/download",
    document_download_controller.download_document,
    methods=["GET"],
    response_class=StreamingResponse,
    operation_id="downloadDocument",
    summary="Descargar documento",
    description="Devuelve el archivo del documento al usuario autenticado, verificando que sea parte del chat.",
    responses=_response,
)
router.add_api_route(
    "/manage/document/{document_id}/download",
    document_download_controller.download_document_manage,
    methods=["GET"],
    response_class=StreamingResponse,
    operation_id="downloadDocumentManage",
    summary="Descargar documento (manage)",
    description="Devuelve el archivo de cualquier documento sin restricción de pertenencia al chat. Requiere permiso de administración.",
    responses=_response,
)
