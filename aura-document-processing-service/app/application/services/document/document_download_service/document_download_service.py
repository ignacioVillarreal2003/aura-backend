import logging
from typing import Optional
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.services.document.document_download_service.document_download_service_settings import (
    DocumentDownloadServiceSettings
)
from app.application.services.document.document_download_service.exceptions.document_download_service_exception import (
    DocumentDownloadInvalidRequestException,
    DocumentDownloadNotFoundException,
    DocumentDownloadServiceException,
    DocumentDownloadStorageException,
)
from app.application.services.document.document_download_service.interfaces.document_download_service_interface import (
    DocumentDownloadServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document_processing_permissions import DocumentProcessingPermissions
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentNotFoundException,
    DocumentStorageException,
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)

logger = logging.getLogger(__name__)


class DocumentDownloadService(DocumentDownloadServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            document_storage: DocumentStorageInterface,
            authorizer: Authorizer,
            document_download_service_settings: Optional[DocumentDownloadServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._document_storage = document_storage
        self._authorizer = authorizer
        self._settings = document_download_service_settings or DocumentDownloadServiceSettings()

    async def download_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> tuple[bytes, str, str]:
        logger.info(
            "Document download was initiated.",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            if document_id <= 0:
                raise DocumentDownloadInvalidRequestException("The document identifier must be a positive number.")
            self._authorizer.require_permissions(
                authenticated_user=authenticated_user,
                required_permissions=frozenset({DocumentProcessingPermissions.DOWNLOAD_DOCUMENT}),
            )

            document = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=database_session
            )
            if document is None:
                logger.warning(
                    "The document was not found.",
                    extra={"document_id": document_id}
                )
                raise DocumentDownloadNotFoundException("The document was not found.")

            try:
                content = await self._document_storage.download_document(
                    object_name=document.storage_url
                )
            except DocumentNotFoundException as e:
                raise DocumentDownloadNotFoundException(
                    "The document file was not found in storage."
                ) from e
            except DocumentStorageException as e:
                raise DocumentDownloadStorageException(
                    "Failed to download the document from storage."
                ) from e

            logger.info(
                "Document downloaded successfully.",
                extra={
                    "document_id": document_id,
                    "user_id": authenticated_user.id,
                    "size_bytes": len(content)
                }
            )

            return content, document.name, document.mime_type.value

        except (
                DocumentDownloadInvalidRequestException,
                DocumentDownloadNotFoundException,
                DocumentDownloadStorageException,
                UnauthorizedException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred during document download.",
                extra={"document_id": document_id}
            )
            raise DocumentDownloadServiceException("Document download failed.") from e


async def get_document_download_service(
        request: Request
) -> DocumentDownloadServiceInterface:
    try:
        return request.app.state.document_download_service
    except AttributeError:
        logger.error("DocumentDownloadService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentDownloadService is not registered on the application state."
        )
