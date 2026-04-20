import logging
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.controllers.document_controllers.document_download_controller.interfaces.download_document_controller_interface import (
    DocumentDownloadControllerInterface
)
from app.application.services.document.document_download_service.document_download_service import (
    get_document_download_service
)
from app.application.services.document.document_download_service.interfaces.document_download_service_interface import (
    DocumentDownloadServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session

logger = logging.getLogger(__name__)


class DocumentDownloadController(DocumentDownloadControllerInterface):
    async def download_document(
            self,
            document_id: int,
            document_download_service: DocumentDownloadServiceInterface = Depends(get_document_download_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> Response:
        logger.info(
            "Handling download document request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        content, filename, mime_type = await document_download_service.download_document(
            document_id=document_id,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Download document completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )


router = APIRouter()
document_download_controller = DocumentDownloadController()

router.get(
    "/document/{document_id}/download",
    response_class=Response
)(document_download_controller.download_document)
