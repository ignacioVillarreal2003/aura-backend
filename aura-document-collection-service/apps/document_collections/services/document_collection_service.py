import logging
from django.db import transaction
from django.db.models import QuerySet

from apps.classification_levels.repositories import classification_level_repository
from apps.compartments.repositories import compartment_repository
from apps.document_collections.models import DocumentCollection
from apps.document_collections.repositories import (
    document_collection_compartment_repository,
    document_collection_repository,
)
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization.permissions import (
    CREATE_DOCUMENT_COLLECTION,
    DELETE_DOCUMENT_COLLECTION,
    GET_DOCUMENT_COLLECTION,
    LIST_DOCUMENT_COLLECTIONS,
    UPDATE_DOCUMENT_COLLECTION,
)
from core.domain.document_collection_exceptions import (
    ClassificationLevelNotFoundException,
    CollectionNotFoundException,
    CompartmentNotFoundException,
)

logger = logging.getLogger(__name__)


class DocumentCollectionService:
    def list_document_collections(self, user: AuthenticatedUser) -> QuerySet[DocumentCollection]:
        AccessControl.require_permission(user, LIST_DOCUMENT_COLLECTIONS)
        return document_collection_repository.list_active()

    @transaction.atomic
    def create_document_collection(
        self,
        user: AuthenticatedUser,
        name: str,
        classification_level_id: int,
        compartment_ids: list[int],
    ) -> DocumentCollection:
        AccessControl.require_permission(user, CREATE_DOCUMENT_COLLECTION)
        if classification_level_repository.get_by_id(classification_level_id) is None:
            raise ClassificationLevelNotFoundException()
        unique_compartment_ids = list(set(compartment_ids))
        if compartment_repository.filter_by_ids(unique_compartment_ids).count() != len(unique_compartment_ids):
            raise CompartmentNotFoundException()
        document_collection = document_collection_repository.create(
            name=name,
            created_by=user.id,
            classification_level_id=classification_level_id,
        )
        for cid in unique_compartment_ids:
            document_collection_compartment_repository.create(
                document_collection_id=document_collection.id,
                compartment_id=cid,
                created_by=user.id,
            )
        logger.info(
            "Document collection created.",
            extra={"document_collection_id": document_collection.id, "user_id": user.id},
        )
        return document_collection_repository.get_active_by_id(document_collection.id)

    def get_document_collection(
        self,
        user: AuthenticatedUser,
        document_collection_id: int,
    ) -> DocumentCollection:
        AccessControl.require_permission(user, GET_DOCUMENT_COLLECTION)
        document_collection = document_collection_repository.get_active_by_id(document_collection_id)
        if document_collection is None:
            raise CollectionNotFoundException()
        return document_collection

    @transaction.atomic
    def update_document_collection(
        self,
        user: AuthenticatedUser,
        document_collection_id: int,
        name: str | None = None,
        classification_level_id: int | None = None,
        compartment_ids: list[int] | None = None,
    ) -> DocumentCollection:
        AccessControl.require_permission(user, UPDATE_DOCUMENT_COLLECTION)
        document_collection = document_collection_repository.get_active_by_id(document_collection_id)
        if document_collection is None:
            raise CollectionNotFoundException()
        if classification_level_id is not None:
            if classification_level_repository.get_by_id(classification_level_id) is None:
                raise ClassificationLevelNotFoundException()
        if compartment_ids is not None:
            unique_compartment_ids = list(set(compartment_ids))
            if compartment_repository.filter_by_ids(unique_compartment_ids).count() != len(unique_compartment_ids):
                raise CompartmentNotFoundException()
            document_collection_compartment_repository.delete_all_by_collection_id(document_collection_id)
            for cid in unique_compartment_ids:
                document_collection_compartment_repository.create(
                    document_collection_id=document_collection_id,
                    compartment_id=cid,
                    created_by=user.id,
                )
        document_collection_repository.update(
            document_collection,
            updated_by=user.id,
            name=name,
            classification_level_id=classification_level_id,
        )
        return document_collection_repository.get_active_by_id(document_collection_id)

    @transaction.atomic
    def delete_document_collection(
        self,
        user: AuthenticatedUser,
        document_collection_id: int,
    ) -> None:
        AccessControl.require_permission(user, DELETE_DOCUMENT_COLLECTION)
        document_collection = document_collection_repository.get_active_by_id(document_collection_id)
        if document_collection is None:
            raise CollectionNotFoundException()
        document_collection_repository.soft_delete(document_collection, deleted_by=user.id)
        logger.info(
            "Document collection deleted.",
            extra={"document_collection_id": document_collection.id, "user_id": user.id},
        )


document_collection_service = DocumentCollectionService()
