import logging

from django.db.models import QuerySet
from django.utils import timezone

from apps.membership.models.chat_membership import ChatMembership

logger = logging.getLogger(__name__)


class MembershipRepository:

    @staticmethod
    def create(member_id: int, chat_id: int, status: str, created_by: int) -> ChatMembership:
        joined_at = timezone.now() if status == "active" else None
        return ChatMembership.objects.create(
            member_id=member_id,
            chat_id=chat_id,
            status=status,
            joined_at=joined_at,
            created_by=created_by,
        )

    @staticmethod
    def get_by_id(membership_id: int) -> ChatMembership | None:
        try:
            return ChatMembership.objects.get(pk=membership_id)
        except ChatMembership.DoesNotExist:
            return None

    @staticmethod
    def get_by_chat_and_member(chat_id: int, member_id: int) -> ChatMembership | None:
        try:
            return ChatMembership.objects.get(chat_id=chat_id, member_id=member_id)
        except ChatMembership.DoesNotExist:
            return None

    @staticmethod
    def list_by_chat(chat_id: int) -> QuerySet[ChatMembership]:
        return ChatMembership.objects.filter(chat_id=chat_id).order_by("created_at")

    @staticmethod
    def is_active_member(chat_id: int, member_id: int) -> bool:
        return ChatMembership.objects.filter(
            chat_id=chat_id,
            member_id=member_id,
            status="active",
        ).exists()

    @staticmethod
    def exists(chat_id: int, member_id: int) -> bool:
        return ChatMembership.objects.all_with_deleted().filter(
            chat_id=chat_id,
            member_id=member_id,
        ).exists()

    @staticmethod
    def update_status(
        membership: ChatMembership,
        new_status: str,
        updated_by: int,
    ) -> ChatMembership:
        membership.status = new_status
        membership.updated_by = updated_by
        membership.updated_at = timezone.now()

        if new_status == "active" and membership.joined_at is None:
            membership.joined_at = timezone.now()
        elif new_status == "inactive":
            membership.left_at = timezone.now()

        membership.save(
            update_fields=["status", "updated_by", "updated_at", "joined_at", "left_at"]
        )
        return membership

    @staticmethod
    def soft_delete(membership: ChatMembership, deleted_by: int) -> None:
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])
        membership.delete(deleted_by=deleted_by)

    @staticmethod
    def get_active_member_ids(chat_id: int) -> list[int]:
        return list(
            ChatMembership.objects
            .filter(chat_id=chat_id, status="active")
            .values_list("member_id", flat=True)
        )


membership_repository = MembershipRepository()
