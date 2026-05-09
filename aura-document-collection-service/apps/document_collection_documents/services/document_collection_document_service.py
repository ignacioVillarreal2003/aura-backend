import logging
from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from apps.document_collection_documents.models import DocumentInDocumentCollection
from apps.document_collection_documents.repositories import (
    document_in_document_collection_repository,
    document_repository,
)
from apps.document_collections.repositories import document_collection_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.domain.document_collection_exceptions import (
    CollectionNotFoundException,
    DocumentLinkNotFoundException,
    DocumentNotAvailableException,
    DuplicateDocumentLinkException,
)
from core.authorization.permissions import (
    ADD_DOCUMENT_COLLECTION_DOCUMENT,
    LIST_DOCUMENT_COLLECTION_DOCUMENTS,
    REMOVE_DOCUMENT_COLLECTION_DOCUMENT,
)

logger = logging.getLogger(__name__)


class DocumentCollectionDocumentService:
    def list_document_collection_documents(
        self,
        user: AuthenticatedUser,
        document_collection_id: int,
    ) -> QuerySet[DocumentInDocumentCollection]:
        AccessControl.require_permission(user, LIST_DOCUMENT_COLLECTION_DOCUMENTS)
        if document_collection_repository.get_active_by_id(document_collection_id) is None:
            raise CollectionNotFoundException()
        return document_in_document_collection_repository.list_active_by_document_collection_id(
            document_collection_id
        )

    @transaction.atomic
    def add_document_collection_document(
        self,
        user: AuthenticatedUser,
        document_collection_id: int,
        document_id: int,
    ) -> DocumentInDocumentCollection:
        AccessControl.require_permission(user, ADD_DOCUMENT_COLLECTION_DOCUMENT)
        document_collection = document_collection_repository.get_active_by_id(document_collection_id)
        if document_collection is None:
            raise CollectionNotFoundException()
        if not document_repository.exists_active_by_id(document_id):
            raise DocumentNotAvailableException()
        existing = document_in_document_collection_repository.get_active_by_document_collection_id_and_document_id(
            document_collection_id=document_collection.id,
            document_id=document_id,
        )
        if existing is not None:
            raise DuplicateDocumentLinkException()
        try:
            link = document_in_document_collection_repository.create(
                document_collection_id=document_collection.id,
                document_id=document_id,
                created_by=user.id,
            )
        except IntegrityError as e:
            raise DuplicateDocumentLinkException() from e
        logger.info(
            "Document linked to document collection.",
            extra={
                "document_collection_id": document_collection_id,
                "document_id": document_id,
                "actor_id": user.id,
            },
        )
        refreshed = document_in_document_collection_repository.get_active_by_id(link.id)
        return refreshed or link

    @transaction.atomic
    def remove_document_collection_document(
        self,
        user: AuthenticatedUser,
        document_collection_id: int,
        document_id: int,
    ) -> None:
        AccessControl.require_permission(user, REMOVE_DOCUMENT_COLLECTION_DOCUMENT)
        document_collection = document_collection_repository.get_active_by_id(document_collection_id)
        if document_collection is None:
            raise CollectionNotFoundException()
        document_in_document_collection = document_in_document_collection_repository.get_active_by_document_collection_id_and_document_id(
            document_collection_id=document_collection.id,
            document_id=document_id,
        )
        if document_in_document_collection is None:
            raise DocumentLinkNotFoundException()
        document_in_document_collection_repository.soft_delete(document_in_document_collection, deleted_by=user.id)
        logger.info(
            "Document unlinked from document collection.",
            extra={
                "document_collection_id": document_collection_id,
                "document_id": document_id,
                "actor_id": user.id,
            },
        )


document_collection_document_service = DocumentCollectionDocumentService()
