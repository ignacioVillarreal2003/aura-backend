from django.db.models import QuerySet
from django.utils import timezone

from apps.document_collection.models import UserInDocumentCollection


class UserInDocumentCollectionRepository:
    @staticmethod
    def list_active_by_document_collection_id(document_collection_id: int) -> QuerySet[UserInDocumentCollection]:
        return (
            UserInDocumentCollection.objects.filter(
                document_collection_id=document_collection_id,
                deleted_at__isnull=True,
            )
            .select_related("document_collection")
            .order_by("id")
        )

    @staticmethod
    def get_active_by_document_collection_id_and_user_id(
        document_collection_id: int,
        user_id: int,
    ) -> UserInDocumentCollection | None:
        return UserInDocumentCollection.objects.filter(
            document_collection_id=document_collection_id,
            user_id=user_id,
            deleted_at__isnull=True,
        ).first()

    @staticmethod
    def create(
        document_collection_id: int,
        user_id: int,
        created_by: int,
    ) -> UserInDocumentCollection:
        return UserInDocumentCollection.objects.create(
            document_collection_id=document_collection_id,
            user_id=user_id,
            created_by=created_by,
            created_at=timezone.now(),
        )

    @staticmethod
    def soft_delete(user_in_document_collection: UserInDocumentCollection, deleted_by: int) -> None:
        user_in_document_collection.deleted_by = deleted_by
        user_in_document_collection.deleted_at = timezone.now()
        user_in_document_collection.save(update_fields=["deleted_by", "deleted_at"])


user_in_document_collection_repository = UserInDocumentCollectionRepository()
