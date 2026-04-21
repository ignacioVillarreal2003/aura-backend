import logging

from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from apps.document_collection_users.models import UserInDocumentCollection
from apps.document_collection_users.repositories import user_in_document_collection_repository
from apps.document_collections.repositories import document_collection_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.domain.document_collection_exceptions import (
    CollectionNotFoundException,
    DuplicateMembershipException,
    UserMembershipNotFoundException,
)
from core.permissions import (
    ADD_DOCUMENT_COLLECTION_USER,
    LIST_DOCUMENT_COLLECTION_USERS,
    REMOVE_DOCUMENT_COLLECTION_USER,
)

logger = logging.getLogger(__name__)


def _permissions_gate(user: AuthenticatedUser, permission: str) -> None:
    AccessControl.require_permissions(user, frozenset({permission}))


class DocumentCollectionUserService:
    def list_document_collection_users(
        self,
        user: AuthenticatedUser,
        document_collection_id: int,
    ) -> QuerySet[UserInDocumentCollection]:
        _permissions_gate(user, LIST_DOCUMENT_COLLECTION_USERS)
        if document_collection_repository.get_active_by_id(document_collection_id) is None:
            raise CollectionNotFoundException()
        return user_in_document_collection_repository.list_active_by_document_collection_id(document_collection_id)

    @transaction.atomic
    def add_document_collection_user(
        self,
        user: AuthenticatedUser,
        document_collection_id: int,
        user_id: int,
    ) -> UserInDocumentCollection:
        _permissions_gate(user, ADD_DOCUMENT_COLLECTION_USER)
        document_collection = document_collection_repository.get_active_by_id(document_collection_id)
        if document_collection is None:
            raise CollectionNotFoundException()
        try:
            user_in_document_collection = user_in_document_collection_repository.create(
                document_collection_id=document_collection.id,
                user_id=user_id,
                created_by=user.id,
            )
        except IntegrityError as e:
            raise DuplicateMembershipException() from e
        logger.info(
            "User added to document collection.",
            extra={
                "document_collection_id": document_collection_id,
                "added_user_id": user_id,
                "actor_id": user.id,
            },
        )
        return user_in_document_collection

    @transaction.atomic
    def remove_document_collection_user(
        self,
        user: AuthenticatedUser,
        document_collection_id: int,
        user_id: int,
    ) -> None:
        _permissions_gate(user, REMOVE_DOCUMENT_COLLECTION_USER)
        document_collection = document_collection_repository.get_active_by_id(document_collection_id)
        if document_collection is None:
            raise CollectionNotFoundException()

        user_in_document_collection = user_in_document_collection_repository.get_active_by_document_collection_id_and_user_id(
            document_collection_id=document_collection.id,
            user_id=user_id,
        )
        if user_in_document_collection is None:
            raise UserMembershipNotFoundException()

        user_in_document_collection_repository.soft_delete(user_in_document_collection, deleted_by=user.id)
        logger.info(
            "User removed from document collection.",
            extra={
                "document_collection_id": document_collection_id,
                "removed_user_id": user_id,
                "actor_id": user.id,
            },
        )


document_collection_user_service = DocumentCollectionUserService()
