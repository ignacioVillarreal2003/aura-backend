import logging
from django.db import IntegrityError
from django.db.models import QuerySet

from apps.classification_levels.models import ClassificationLevel
from apps.classification_levels.repositories import classification_level_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization.permissions import (
    CREATE_CLASSIFICATION_LEVEL,
    DELETE_CLASSIFICATION_LEVEL,
    GET_CLASSIFICATION_LEVEL,
    LIST_CLASSIFICATION_LEVELS,
    UPDATE_CLASSIFICATION_LEVEL,
)
from core.domain.document_collection_exceptions import (
    ClassificationLevelInUseException,
    ClassificationLevelNotFoundException,
    DuplicateClassificationLevelException,
)

logger = logging.getLogger(__name__)


class ClassificationLevelService:
    def list_classification_levels(self, user: AuthenticatedUser) -> QuerySet[ClassificationLevel]:
        AccessControl.require_permission(user, LIST_CLASSIFICATION_LEVELS)
        return classification_level_repository.list_all()

    def get_classification_level(
        self,
        user: AuthenticatedUser,
        classification_level_id: int,
    ) -> ClassificationLevel:
        AccessControl.require_permission(user, GET_CLASSIFICATION_LEVEL)
        obj = classification_level_repository.get_by_id(classification_level_id)
        if obj is None:
            raise ClassificationLevelNotFoundException()
        return obj

    def create_classification_level(
        self,
        user: AuthenticatedUser,
        name: str,
        rank: int,
        description: str = '',
    ) -> ClassificationLevel:
        AccessControl.require_permission(user, CREATE_CLASSIFICATION_LEVEL)
        try:
            obj = classification_level_repository.create(name=name, rank=rank, description=description)
        except IntegrityError as e:
            raise DuplicateClassificationLevelException() from e
        logger.info(
            "Classification level created.",
            extra={"classification_level_id": obj.id, "user_id": user.id},
        )
        return obj

    def update_classification_level(
        self,
        user: AuthenticatedUser,
        classification_level_id: int,
        **kwargs: object,
    ) -> ClassificationLevel:
        AccessControl.require_permission(user, UPDATE_CLASSIFICATION_LEVEL)
        obj = classification_level_repository.get_by_id(classification_level_id)
        if obj is None:
            raise ClassificationLevelNotFoundException()
        name = kwargs.get("name", obj.name)
        rank = kwargs.get("rank", obj.rank)
        description = kwargs.get("description", None)
        try:
            return classification_level_repository.update(obj, name=name, rank=rank, description=description)
        except IntegrityError as e:
            raise DuplicateClassificationLevelException() from e

    def delete_classification_level(
        self,
        user: AuthenticatedUser,
        classification_level_id: int,
    ) -> None:
        AccessControl.require_permission(user, DELETE_CLASSIFICATION_LEVEL)
        obj = classification_level_repository.get_by_id(classification_level_id)
        if obj is None:
            raise ClassificationLevelNotFoundException()
        try:
            classification_level_repository.delete(obj)
        except IntegrityError as e:
            raise ClassificationLevelInUseException() from e
        logger.info(
            "Classification level deleted.",
            extra={"classification_level_id": classification_level_id, "user_id": user.id},
        )


classification_level_service = ClassificationLevelService()
