import logging
from django.db import IntegrityError
from django.db.models import QuerySet

from apps.compartments.models import Compartment
from apps.compartments.repositories import compartment_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization.permissions import (
    CREATE_COMPARTMENT,
    DELETE_COMPARTMENT,
    GET_COMPARTMENT,
    LIST_COMPARTMENTS,
    UPDATE_COMPARTMENT,
)
from core.domain.document_collection_exceptions import (
    CompartmentInUseException,
    CompartmentNotFoundException,
    DuplicateCompartmentException,
)

logger = logging.getLogger(__name__)


class CompartmentService:
    def list_compartments(self, user: AuthenticatedUser) -> QuerySet[Compartment]:
        AccessControl.require_permission(user, LIST_COMPARTMENTS)
        return compartment_repository.list_all()

    def get_compartment(self, user: AuthenticatedUser, compartment_id: int) -> Compartment:
        AccessControl.require_permission(user, GET_COMPARTMENT)
        obj = compartment_repository.get_by_id(compartment_id)
        if obj is None:
            raise CompartmentNotFoundException()
        return obj

    def create_compartment(
        self,
        user: AuthenticatedUser,
        name: str,
        description: str,
    ) -> Compartment:
        AccessControl.require_permission(user, CREATE_COMPARTMENT)
        try:
            obj = compartment_repository.create(name=name, description=description)
        except IntegrityError as e:
            raise DuplicateCompartmentException() from e
        logger.info(
            "Compartment created.",
            extra={"compartment_id": obj.id, "user_id": user.id},
        )
        return obj

    def update_compartment(
        self,
        user: AuthenticatedUser,
        compartment_id: int,
        **kwargs: object,
    ) -> Compartment:
        AccessControl.require_permission(user, UPDATE_COMPARTMENT)
        obj = compartment_repository.get_by_id(compartment_id)
        if obj is None:
            raise CompartmentNotFoundException()
        name = kwargs.get("name", obj.name)
        description = kwargs.get("description", obj.description)
        try:
            return compartment_repository.update(obj, name=name, description=description)
        except IntegrityError as e:
            raise DuplicateCompartmentException() from e

    def delete_compartment(self, user: AuthenticatedUser, compartment_id: int) -> None:
        AccessControl.require_permission(user, DELETE_COMPARTMENT)
        obj = compartment_repository.get_by_id(compartment_id)
        if obj is None:
            raise CompartmentNotFoundException()
        try:
            compartment_repository.delete(obj)
        except IntegrityError as e:
            raise CompartmentInUseException() from e
        logger.info(
            "Compartment deleted.",
            extra={"compartment_id": compartment_id, "user_id": user.id},
        )


compartment_service = CompartmentService()
