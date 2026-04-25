from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.controllers.document.document_download.download_document_controller_interface import (
    DocumentDownloadControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.services.document.document_download_service.document_download_service import (
    get_document_download_service,
)
from app.application.services.document.document_download_service.interfaces.document_download_service_interface import (
    DocumentDownloadServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session


class DocumentDownloadController(DocumentDownloadControllerInterface):
    async def download_document(
            self,
            document_id: int,
            document_download_service: DocumentDownloadServiceInterface = Depends(get_document_download_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> Response:
        content, filename, mime_type = await document_download_service.download_document(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user,
        )
        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": filename,
            },
        )


router = APIRouter()
document_download_controller = DocumentDownloadController()

_error = default_error_responses(
    include_404=False,
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
    response_class=Response,
    operation_id="downloadDocument",
    summary="Descargar documento",
    description="Devuelve el archivo del documento con su tipo MIME.",
    responses=_response,
)
