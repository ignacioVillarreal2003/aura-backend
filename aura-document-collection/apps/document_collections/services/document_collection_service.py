import logging

from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from apps.document_collections.exceptions import (
    CannotRemoveOwnerException,
    CollectionAccessDeniedException,
    CollectionNotFoundException,
    CollectionOwnerRequiredException,
    DocumentLinkNotFoundException,
    DocumentNotAvailableException,
    DuplicateDocumentLinkException,
    DuplicateMembershipException,
    OwnerCannotLeaveException,
    UserMembershipNotFoundException,
)
from apps.document_collections.models import (
    DocumentCollection,
    DocumentInDocumentCollection,
    UserInDocumentCollection,
)
from apps.document_collections.repositories import (
    document_collection_repository,
    document_link_repository,
    document_read_repository,
    user_membership_repository,
)
from core.authentication.authenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)


class DocumentCollectionService:
    def list_collections(self, user: AuthenticatedUser) -> QuerySet[DocumentCollection]:
        return document_collection_repository.list_for_user(user.id)

    @transaction.atomic
    def create_collection(self, user: AuthenticatedUser, name: str) -> DocumentCollection:
        collection = document_collection_repository.create(name=name, created_by=user.id)
        user_membership_repository.create(
            collection_id=collection.id,
            user_id=user.id,
            created_by=user.id,
        )
        logger.info(
            "Document collection created.",
            extra={"collection_id": collection.id, "user_id": user.id},
        )
        return collection

    def get_collection(self, user: AuthenticatedUser, collection_id: int) -> DocumentCollection:
        collection = document_collection_repository.get_active_readonly(collection_id)
        if collection is None:
            raise CollectionNotFoundException()
        self._require_active_member(user, collection_id)
        return collection

    def update_collection(
        self,
        user: AuthenticatedUser,
        collection_id: int,
        *,
        name: str,
    ) -> DocumentCollection:
        collection = document_collection_repository.get_active_readonly(collection_id)
        if collection is None:
            raise CollectionNotFoundException()
        self._require_owner(user, collection)
        return document_collection_repository.update_name(
            collection, name=name, updated_by=user.id
        )

    def delete_collection(self, user: AuthenticatedUser, collection_id: int) -> None:
        collection = document_collection_repository.get_active_readonly(collection_id)
        if collection is None:
            raise CollectionNotFoundException()
        self._require_owner(user, collection)
        document_collection_repository.soft_delete(collection, deleted_by=user.id)
        logger.info(
            "Document collection deleted.",
            extra={"collection_id": collection_id, "user_id": user.id},
        )

    def list_users(
        self,
        user: AuthenticatedUser,
        collection_id: int,
    ) -> QuerySet[UserInDocumentCollection]:
        self._get_collection_for_member(user, collection_id)
        return user_membership_repository.list_active(collection_id)

    @transaction.atomic
    def add_user(
        self,
        user: AuthenticatedUser,
        collection_id: int,
        *,
        user_id_to_add: int,
    ) -> UserInDocumentCollection:
        collection = self._get_collection_for_owner(user, collection_id)
        try:
            membership = user_membership_repository.create(
                collection_id=collection.id,
                user_id=user_id_to_add,
                created_by=user.id,
            )
        except IntegrityError as e:
            raise DuplicateMembershipException() from e
        logger.info(
            "User added to document collection.",
            extra={
                "collection_id": collection_id,
                "added_user_id": user_id_to_add,
                "actor_id": user.id,
            },
        )
        return membership

    @transaction.atomic
    def remove_user_membership(
        self,
        user: AuthenticatedUser,
        collection_id: int,
        link_id: int,
    ) -> None:
        collection = document_collection_repository.get_active_readonly(collection_id)
        if collection is None:
            raise CollectionNotFoundException()

        membership = user_membership_repository.get_active(
            collection_id=collection_id, link_id=link_id
        )
        if membership is None:
            raise UserMembershipNotFoundException()

        is_self = membership.user_id == user.id
        is_owner = collection.created_by == user.id

        if is_self:
            if collection.created_by == user.id:
                raise OwnerCannotLeaveException()
        else:
            if not is_owner:
                raise CollectionOwnerRequiredException(
                    "Only the collection owner can remove other members"
                )
            if membership.user_id == collection.created_by:
                raise CannotRemoveOwnerException()

        user_membership_repository.soft_delete(membership, deleted_by=user.id)
        logger.info(
            "User removed from document collection.",
            extra={
                "collection_id": collection_id,
                "membership_id": link_id,
                "actor_id": user.id,
            },
        )

    def list_documents(
        self,
        user: AuthenticatedUser,
        collection_id: int,
    ) -> QuerySet[DocumentInDocumentCollection]:
        self._get_collection_for_member(user, collection_id)
        return document_link_repository.list_active(collection_id)

    @transaction.atomic
    def add_document(
        self,
        user: AuthenticatedUser,
        collection_id: int,
        *,
        document_id: int,
    ) -> DocumentInDocumentCollection:
        collection = self._get_collection_for_owner(user, collection_id)
        if not document_read_repository.exists_active(document_id):
            raise DocumentNotAvailableException()
        try:
            link = document_link_repository.create(
                collection_id=collection.id,
                document_id=document_id,
                created_by=user.id,
            )
        except IntegrityError as e:
            raise DuplicateDocumentLinkException() from e
        logger.info(
            "Document linked to collection.",
            extra={
                "collection_id": collection_id,
                "document_id": document_id,
                "actor_id": user.id,
            },
        )
        return link

    @transaction.atomic
    def remove_document_link(
        self,
        user: AuthenticatedUser,
        collection_id: int,
        link_id: int,
    ) -> None:
        collection = self._get_collection_for_owner(user, collection_id)
        link = document_link_repository.get_active(collection_id=collection.id, link_id=link_id)
        if link is None:
            raise DocumentLinkNotFoundException()
        document_link_repository.soft_delete(link, deleted_by=user.id)
        logger.info(
            "Document unlinked from collection.",
            extra={
                "collection_id": collection_id,
                "link_id": link_id,
                "actor_id": user.id,
            },
        )

    def _require_active_member(self, user: AuthenticatedUser, collection_id: int) -> None:
        if not user_membership_repository.is_active_member(
            collection_id=collection_id, user_id=user.id
        ):
            raise CollectionAccessDeniedException()

    def _require_owner(self, user: AuthenticatedUser, collection: DocumentCollection) -> None:
        if collection.created_by != user.id:
            raise CollectionOwnerRequiredException()

    def _get_collection_for_member(
        self,
        user: AuthenticatedUser,
        collection_id: int,
    ) -> DocumentCollection:
        collection = document_collection_repository.get_active_readonly(collection_id)
        if collection is None:
            raise CollectionNotFoundException()
        self._require_active_member(user, collection_id)
        return collection

    def _get_collection_for_owner(
        self,
        user: AuthenticatedUser,
        collection_id: int,
    ) -> DocumentCollection:
        collection = document_collection_repository.get_active_readonly(collection_id)
        if collection is None:
            raise CollectionNotFoundException()
        self._require_owner(user, collection)
        return collection


document_collection_service = DocumentCollectionService()
