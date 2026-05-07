from django.utils import timezone

from apps.user_authorizations.models import UserClearance


class UserClearanceRepository:
    def get_by_user_id(self, user_id: int) -> UserClearance | None:
        return (
            UserClearance.objects
            .select_related("classification_level")
            .filter(user_id=user_id)
            .first()
        )

    def set(self, user_id: int, classification_level_id: int, created_by: int) -> UserClearance:
        obj, created = UserClearance.objects.get_or_create(
            user_id=user_id,
            defaults={
                "classification_level_id": classification_level_id,
                "created_by": created_by,
            },
        )
        if not created:
            obj.classification_level_id = classification_level_id
            obj.created_by = created_by
            obj.created_at = timezone.now()
            obj.save(update_fields=["classification_level_id", "created_by", "created_at"])
        return obj

    def delete_by_user_id(self, user_id: int) -> bool:
        deleted, _ = UserClearance.objects.filter(user_id=user_id).delete()
        return deleted > 0


user_clearance_repository = UserClearanceRepository()
