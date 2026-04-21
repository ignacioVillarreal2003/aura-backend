import logging

from django.db import transaction
from django.db.models import QuerySet

from apps.document_collections.models import DocumentCollection
from apps.document_collections.repositories import document_collection_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.domain.document_collection_exceptions import CollectionNotFoundException
from core.permissions import (
    CREATE_DOCUMENT_COLLECTION,
    DELETE_DOCUMENT_COLLECTION,
    GET_DOCUMENT_COLLECTION,
    LIST_DOCUMENT_COLLECTIONS,
    UPDATE_DOCUMENT_COLLECTION,
)

logger = logging.getLogger(__name__)


def _permissions_gate(user: AuthenticatedUser, permission: str) -> None:
    AccessControl.require_permissions(user, frozenset({permission}))


class DocumentCollectionService:
    def list_document_collections(self, user: AuthenticatedUser) -> QuerySet[DocumentCollection]:
        _permissions_gate(user, LIST_DOCUMENT_COLLECTIONS)
        return document_collection_repository.list_active()

    @transaction.atomic
    def create_document_collection(self, user: AuthenticatedUser, name: str) -> DocumentCollection:
        _permissions_gate(user, CREATE_DOCUMENT_COLLECTION)
        document_collection = document_collection_repository.create(name=name, created_by=user.id)
        logger.info(
            "Document collection created.",
            extra={"document_collection_id": document_collection.id, "user_id": user.id},
        )
        return document_collection

    def get_document_collection(self, user: AuthenticatedUser, document_collection_id: int) -> DocumentCollection:
        _permissions_gate(user, GET_DOCUMENT_COLLECTION)
        document_collection = document_collection_repository.get_active_by_id(document_collection_id)
        if document_collection is None:
            raise CollectionNotFoundException()
        return document_collection

    @transaction.atomic
    def update_document_collection(
        self,
        user: AuthenticatedUser,
        document_collection_id: int,
        name: str,
    ) -> DocumentCollection:
        _permissions_gate(user, UPDATE_DOCUMENT_COLLECTION)
        document_collection = document_collection_repository.get_active_by_id(document_collection_id)
        if document_collection is None:
            raise CollectionNotFoundException()
        return document_collection_repository.update(
            document_collection,
            name=name,
            updated_by=user.id,
        )

    @transaction.atomic
    def delete_document_collection(self, user: AuthenticatedUser, document_collection_id: int) -> None:
        _permissions_gate(user, DELETE_DOCUMENT_COLLECTION)
        document_collection = document_collection_repository.get_active_by_id(document_collection_id)
        if document_collection is None:
            raise CollectionNotFoundException()
        document_collection_repository.soft_delete(document_collection, deleted_by=user.id)
        logger.info(
            "Document collection deleted.",
            extra={"document_collection_id": document_collection.id, "user_id": user.id},
        )


document_collection_service = DocumentCollectionService()
