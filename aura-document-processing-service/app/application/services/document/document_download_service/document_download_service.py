import logging
from typing import AsyncIterator, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.services.document.document_download_service.document_download_service_settings import (
    DocumentDownloadServiceSettings,
)
from app.application.services.document.document_download_service.exceptions.document_download_service_exception import (
    DocumentDownloadInvalidRequestException,
    DocumentDownloadNotFoundException,
    DocumentDownloadNotReadyException,
    DocumentDownloadServiceException,
    DocumentDownloadStorageException,
)
from app.application.services.document.document_download_service.interfaces.document_download_service_interface import (
    DocumentDownloadServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.document_mime_type import DocumentMimeType
from app.domain.constants.document.document_status import DocumentStatus
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.chat_membership.interfaces.chat_membership_provider_interface import (
    ChatMembershipProviderInterface,
)
from app.infrastructure.http.document_collection_catalog.interfaces.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentNotFoundException,
    DocumentStorageException,
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface,
)

logger = logging.getLogger(__name__)


class DocumentDownloadService(DocumentDownloadServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            document_storage: DocumentStorageInterface,
            document_collection_catalog_client: DocumentCollectionCatalogClientInterface,
            chat_membership_provider: ChatMembershipProviderInterface,
            document_download_service_settings: Optional[DocumentDownloadServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._document_storage = document_storage
        self._document_collection_catalog_client = document_collection_catalog_client
        self._chat_membership_provider = chat_membership_provider
        self._settings = document_download_service_settings or DocumentDownloadServiceSettings()

    async def download_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> tuple[AsyncIterator[bytes], str, str]:
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

            document = await self._get_document_or_raise(document_id, database_session)

            await self._require_document_access(document, authenticated_user)

            return await self._stream_document(document, authenticated_user.id)

        except (
                DocumentDownloadInvalidRequestException,
                DocumentDownloadNotFoundException,
                DocumentDownloadNotReadyException,
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

    async def download_document_manage(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> tuple[AsyncIterator[bytes], str, str]:
        logger.info(
            "Manage document download was initiated.",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            if document_id <= 0:
                raise DocumentDownloadInvalidRequestException("The document identifier must be a positive number.")

            document = await self._get_document_or_raise(document_id, database_session)

            return await self._stream_document(document, authenticated_user.id)

        except (
                DocumentDownloadInvalidRequestException,
                DocumentDownloadNotFoundException,
                DocumentDownloadNotReadyException,
                DocumentDownloadStorageException,
                UnauthorizedException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred during manage document download.",
                extra={"document_id": document_id}
            )
            raise DocumentDownloadServiceException("Document download failed.") from e

    async def _get_document_or_raise(
            self,
            document_id: int,
            database_session: AsyncSession,
    ) -> Document:
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

        status_str = document.status.value if hasattr(document.status, "value") else document.status
        if status_str == DocumentStatus.uploaded.value:
            logger.warning(
                "The document is not ready for download.",
                extra={"document_id": document_id, "status": status_str}
            )
            raise DocumentDownloadNotReadyException(
                "The document is still being processed and is not yet available for download."
            )

        return document

    async def _require_document_access(
            self,
            document: Document,
            authenticated_user: AuthenticatedUser,
    ) -> None:
        token = get_request_token()

        accessible_ids = await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
            user_id=int(authenticated_user.id),
            authorization_header=token,
        )
        if int(document.id) in accessible_ids:
            return

        if document.chat_id is not None:
            membership = await self._chat_membership_provider.get_membership(
                chat_id=int(document.chat_id),
                user_id=int(authenticated_user.id),
                authorization_header=token,
            )
            if membership.is_member:
                return

        logger.warning(
            "Unauthorized document download attempt.",
            extra={
                "document_id": document.id,
                "user_id": authenticated_user.id,
            },
        )
        raise UnauthorizedException("You are not authorized to download this document.")

    async def _stream_document(
            self,
            document: Document,
            user_id: int,
    ) -> tuple[AsyncIterator[bytes], str, str]:
        try:
            content_stream = self._document_storage.download_document_stream(
                object_name=document.storage_url,
                chunk_size=self._settings.download_chunk_size_bytes,
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
                "document_id": document.id,
                "user_id": user_id,
                "chunk_size_bytes": self._settings.download_chunk_size_bytes
            }
        )

        mime_str = (
            document.mime_type.value
            if hasattr(document.mime_type, "value")
            else document.mime_type
        )

        try:
            document_mime_type = DocumentMimeType(mime_str)
            media_type = document_mime_type.media_type
            filename = self._ensure_filename_extension(document.name, document_mime_type.extension)
        except ValueError:
            media_type = "application/octet-stream"
            filename = document.name

        return content_stream, filename, media_type

    @staticmethod
    def _ensure_filename_extension(filename: str, extension: str) -> str:
        if filename.lower().endswith(extension.lower()):
            return filename
        return f"{filename}{extension}"
