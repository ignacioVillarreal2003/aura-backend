from django.db.models import QuerySet
from django.utils import timezone

from apps.document_collections.models import UserInDocumentCollection


class UserMembershipRepository:
    def is_active_member(self, *, collection_id: int, user_id: int) -> bool:
        return UserInDocumentCollection.objects.filter(
            document_collection_id=collection_id,
            user_id=user_id,
            deleted_at__isnull=True,
        ).exists()

    def list_active(self, collection_id: int) -> QuerySet[UserInDocumentCollection]:
        return (
            UserInDocumentCollection.objects.filter(
                document_collection_id=collection_id,
                deleted_at__isnull=True,
            )
            .select_related("document_collection")
            .order_by("id")
        )

    def get_active(self, *, collection_id: int, link_id: int) -> UserInDocumentCollection | None:
        return UserInDocumentCollection.objects.filter(
            pk=link_id,
            document_collection_id=collection_id,
            deleted_at__isnull=True,
        ).first()

    def create(
        self,
        *,
        collection_id: int,
        user_id: int,
        created_by: int,
    ) -> UserInDocumentCollection:
        now = timezone.now()
        return UserInDocumentCollection.objects.create(
            document_collection_id=collection_id,
            user_id=user_id,
            created_by=created_by,
            created_at=now,
        )

    def soft_delete(self, membership: UserInDocumentCollection, *, deleted_by: int) -> None:
        now = timezone.now()
        membership.deleted_by = deleted_by
        membership.deleted_at = now
        membership.save(update_fields=["deleted_by", "deleted_at"])


user_membership_repository = UserMembershipRepository()
