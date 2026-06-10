import logging

from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from apps.classification_levels.repositories import classification_level_repository
from apps.compartments.repositories import compartment_repository
from apps.document_collection_documents.models import DocumentInDocumentCollection
from apps.document_collection_documents.repositories import document_in_document_collection_repository
from apps.document_collections.models import DocumentCollection
from apps.document_collections.repositories import document_collection_repository
from apps.user_authorizations.models import UserClearance, UserCompartment
from apps.user_authorizations.repositories import (
    user_clearance_repository,
    user_compartment_repository,
)
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization.permissions import (
    ADD_USER_COMPARTMENT,
    DELETE_USER_CLEARANCE,
    GET_USER_AUTHORIZATION,
    GET_USER_ACCESSIBLE_COLLECTIONS,
    GET_USER_ACCESSIBLE_DOCUMENTS,
    LIST_USER_COMPARTMENTS,
    REMOVE_USER_COMPARTMENT,
    SET_USER_CLEARANCE,
)
from core.domain.document_collection_exceptions import (
    ClassificationLevelNotFoundException,
    CompartmentNotFoundException,
    DuplicateUserCompartmentException,
    UserClearanceNotFoundException,
    UserCompartmentNotFoundException,
)

logger = logging.getLogger(__name__)


class UserAuthorizationService:
    def get_user_authorization(
        self,
        user: AuthenticatedUser,
        target_user_id: int,
    ) -> dict:
        AccessControl.require_permission(user, GET_USER_AUTHORIZATION)
        clearance = user_clearance_repository.get_by_user_id(target_user_id)
        compartments = user_compartment_repository.list_by_user_id(target_user_id)
        return {
            "user_id": target_user_id,
            "clearance": clearance,
            "compartments": list(compartments),
        }

    @transaction.atomic
    def set_user_clearance(
        self,
        user: AuthenticatedUser,
        target_user_id: int,
        classification_level_id: int,
    ) -> UserClearance:
        AccessControl.require_permission(user, SET_USER_CLEARANCE)
        if classification_level_repository.get_by_id(classification_level_id) is None:
            raise ClassificationLevelNotFoundException()
        user_clearance_repository.set(
            user_id=target_user_id,
            classification_level_id=classification_level_id,
            created_by=user.id,
        )
        logger.info(
            "User clearance set.",
            extra={
                "target_user_id": target_user_id,
                "classification_level_id": classification_level_id,
                "actor_id": user.id,
            },
        )
        return user_clearance_repository.get_by_user_id(target_user_id)

    @transaction.atomic
    def delete_user_clearance(
        self,
        user: AuthenticatedUser,
        target_user_id: int,
    ) -> None:
        AccessControl.require_permission(user, DELETE_USER_CLEARANCE)
        deleted = user_clearance_repository.delete_by_user_id(target_user_id)
        if not deleted:
            raise UserClearanceNotFoundException()
        logger.info(
            "User clearance deleted.",
            extra={"target_user_id": target_user_id, "actor_id": user.id},
        )

    def list_user_compartments(
        self,
        user: AuthenticatedUser,
        target_user_id: int,
    ) -> QuerySet[UserCompartment]:
        AccessControl.require_permission(user, LIST_USER_COMPARTMENTS)
        return user_compartment_repository.list_by_user_id(target_user_id)

    @transaction.atomic
    def add_user_compartment(
        self,
        user: AuthenticatedUser,
        target_user_id: int,
        compartment_id: int,
    ) -> UserCompartment:
        AccessControl.require_permission(user, ADD_USER_COMPARTMENT)
        if compartment_repository.get_by_id(compartment_id) is None:
            raise CompartmentNotFoundException()
        existing = user_compartment_repository.get_by_user_id_and_compartment_id(
            user_id=target_user_id,
            compartment_id=compartment_id,
        )
        if existing is not None:
            raise DuplicateUserCompartmentException()
        try:
            entry = user_compartment_repository.create(
                user_id=target_user_id,
                compartment_id=compartment_id,
                created_by=user.id,
            )
        except IntegrityError as e:
            raise DuplicateUserCompartmentException() from e
        logger.info(
            "User compartment added.",
            extra={
                "target_user_id": target_user_id,
                "compartment_id": compartment_id,
                "actor_id": user.id,
            },
        )
        return entry

    @transaction.atomic
    def remove_user_compartment(
        self,
        user: AuthenticatedUser,
        target_user_id: int,
        compartment_id: int,
    ) -> None:
        AccessControl.require_permission(user, REMOVE_USER_COMPARTMENT)
        entry = user_compartment_repository.get_by_user_id_and_compartment_id(
            user_id=target_user_id,
            compartment_id=compartment_id,
        )
        if entry is None:
            raise UserCompartmentNotFoundException()
        user_compartment_repository.delete(entry)
        logger.info(
            "User compartment removed.",
            extra={
                "target_user_id": target_user_id,
                "compartment_id": compartment_id,
                "actor_id": user.id,
            },
        )

    def get_accessible_collections(
        self,
        user: AuthenticatedUser,
        target_user_id: int,
    ) -> QuerySet[DocumentCollection]:
        AccessControl.require_permission(user, GET_USER_ACCESSIBLE_COLLECTIONS)
        clearance = user_clearance_repository.get_by_user_id(target_user_id)
        if clearance is None:
            return DocumentCollection.objects.none()
        compartment_ids = user_compartment_repository.list_compartment_ids_by_user_id(target_user_id)
        return document_collection_repository.list_accessible(
            max_rank=clearance.classification_level.rank,
            compartment_ids=compartment_ids,
        )

    def get_accessible_documents(
        self,
        user: AuthenticatedUser,
        target_user_id: int,
    ) -> QuerySet[DocumentInDocumentCollection]:
        AccessControl.require_permission(user, GET_USER_ACCESSIBLE_DOCUMENTS)
        clearance = user_clearance_repository.get_by_user_id(target_user_id)
        if clearance is None:
            return DocumentInDocumentCollection.objects.none()
        compartment_ids = user_compartment_repository.list_compartment_ids_by_user_id(target_user_id)
        accessible_collections = document_collection_repository.list_accessible(
            max_rank=clearance.classification_level.rank,
            compartment_ids=compartment_ids,
        )
        collection_ids = list(accessible_collections.values_list("id", flat=True))
        return document_in_document_collection_repository.list_accessible_by_collection_ids(collection_ids)


user_authorization_service = UserAuthorizationService()
