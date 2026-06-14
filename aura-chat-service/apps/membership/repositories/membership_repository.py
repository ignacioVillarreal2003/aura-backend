import logging
from django.db.models import QuerySet
from django.utils import timezone

from apps.membership.models.chat_membership import ChatMembership

logger = logging.getLogger(__name__)


class MembershipRepository:
    @staticmethod
    def create(member_id: int, chat_id: int, status: str, created_by: int, role: str = ChatMembership.Role.EDITOR) -> ChatMembership:
        joined_at = timezone.now() if status == ChatMembership.Status.ACTIVE else None
        return ChatMembership.objects.create(
            member_id=member_id,
            chat_id=chat_id,
            status=status,
            role=role,
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
    def get_by_chat_and_member_for_update(chat_id: int, member_id: int) -> ChatMembership | None:
        try:
            return ChatMembership.objects.select_for_update().get(
                chat_id=chat_id, member_id=member_id
            )
        except ChatMembership.DoesNotExist:
            return None

    @staticmethod
    def list_by_member(member_id: int, status: str | None = None) -> QuerySet[ChatMembership]:
        qs = ChatMembership.objects.select_related('chat').filter(member_id=member_id).order_by("-created_at")
        if status is not None:
            qs = qs.filter(status=status)
        return qs

    @staticmethod
    def list_by_chat(chat_id: int, status: str | None = None) -> QuerySet[ChatMembership]:
        qs = ChatMembership.objects.select_related('chat').filter(chat_id=chat_id).order_by("created_at")
        if status is not None:
            qs = qs.filter(status=status)
        return qs

    @staticmethod
    def is_active_member(chat_id: int, member_id: int) -> bool:
        return ChatMembership.objects.filter(
            chat_id=chat_id,
            member_id=member_id,
            status=ChatMembership.Status.ACTIVE,
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

        if new_status == ChatMembership.Status.ACTIVE and membership.joined_at is None:
            membership.joined_at = timezone.now()

        membership.save(
            update_fields=["status", "updated_by", "updated_at", "joined_at"]
        )
        return membership

    @staticmethod
    def soft_delete(membership: ChatMembership, deleted_by: int) -> None:
        now = timezone.now()
        membership.left_at = now
        membership.deleted_at = now
        membership.deleted_by = deleted_by
        membership.save(update_fields=["left_at", "deleted_at", "deleted_by"])

    @staticmethod
    def get_active_member_ids(chat_id: int) -> list[int]:
        return list(
            ChatMembership.objects
            .filter(chat_id=chat_id, status=ChatMembership.Status.ACTIVE)
            .values_list("member_id", flat=True)
        )

    @staticmethod
    def mark_as_read(chat_id: int, member_id: int) -> None:
        ChatMembership.objects.filter(
            chat_id=chat_id,
            member_id=member_id,
            status=ChatMembership.Status.ACTIVE,
        ).update(last_read_at=timezone.now())

    @staticmethod
    def get_active_member_ids_in(chat_id: int, member_ids: list[int]) -> set[int]:
        return set(
            ChatMembership.objects
            .filter(chat_id=chat_id, member_id__in=member_ids, status=ChatMembership.Status.ACTIVE)
            .values_list("member_id", flat=True)
        )

    @staticmethod
    def get_existing_member_ids_in(chat_id: int, member_ids: list[int]) -> set[int]:
        """Returns active/pending (non-soft-deleted) member IDs in the given set."""
        return set(
            ChatMembership.objects
            .filter(chat_id=chat_id, member_id__in=member_ids)
            .values_list("member_id", flat=True)
        )

    @staticmethod
    def get_active_chat_ids_for_member(member_id: int, chat_ids: list[int]) -> set[int]:
        return set(
            ChatMembership.objects
            .filter(member_id=member_id, chat_id__in=chat_ids, status=ChatMembership.Status.ACTIVE)
            .values_list("chat_id", flat=True)
        )

    @staticmethod
    def update_role(chat_id: int, member_id: int, role: str, updated_by: int) -> ChatMembership | None:
        membership = ChatMembership.objects.select_for_update().filter(
            chat_id=chat_id,
            member_id=member_id,
            status=ChatMembership.Status.ACTIVE,
        ).first()
        if membership is None:
            return None
        membership.role = role
        membership.updated_by = updated_by
        membership.updated_at = timezone.now()
        membership.save(update_fields=["role", "updated_by", "updated_at"])
        return membership

    @staticmethod
    def get_role(chat_id: int, member_id: int) -> str | None:
        result = ChatMembership.objects.filter(
            chat_id=chat_id,
            member_id=member_id,
            status=ChatMembership.Status.ACTIVE,
        ).values_list("role", flat=True).first()
        return result

    @staticmethod
    def is_active_contributor(chat_id: int, member_id: int) -> bool:
        """Returns True for active members with owner or editor role (can make changes)."""
        return ChatMembership.objects.filter(
            chat_id=chat_id,
            member_id=member_id,
            status=ChatMembership.Status.ACTIVE,
            role__in=[ChatMembership.Role.OWNER, ChatMembership.Role.EDITOR],
        ).exists()

    @staticmethod
    def is_chat_owner(chat_id: int, member_id: int) -> bool:
        return ChatMembership.objects.filter(
            chat_id=chat_id,
            member_id=member_id,
            status=ChatMembership.Status.ACTIVE,
            role=ChatMembership.Role.OWNER,
        ).exists()

    @staticmethod
    def pin(chat_id: int, member_id: int) -> None:
        ChatMembership.objects.filter(
            chat_id=chat_id,
            member_id=member_id,
            status=ChatMembership.Status.ACTIVE,
        ).update(pinned_at=timezone.now())

    @staticmethod
    def unpin(chat_id: int, member_id: int) -> None:
        ChatMembership.objects.filter(
            chat_id=chat_id,
            member_id=member_id,
            status=ChatMembership.Status.ACTIVE,
        ).update(pinned_at=None)

    @staticmethod
    def archive_chats(chat_ids: list[int], member_id: int) -> int:
        return ChatMembership.objects.filter(
            chat_id__in=chat_ids,
            member_id=member_id,
            status=ChatMembership.Status.ACTIVE,
            archived_at__isnull=True,
        ).update(archived_at=timezone.now())

    @staticmethod
    def unarchive_chats(chat_ids: list[int], member_id: int) -> int:
        return ChatMembership.objects.filter(
            chat_id__in=chat_ids,
            member_id=member_id,
            status=ChatMembership.Status.ACTIVE,
            archived_at__isnull=False,
        ).update(archived_at=None)

    @staticmethod
    def soft_delete_by_chat(chat_id: int, deleted_by: int) -> None:
        now = timezone.now()
        ChatMembership.objects.filter(chat_id=chat_id).update(
            left_at=now,
            deleted_at=now,
            deleted_by=deleted_by,
        )


membership_repository = MembershipRepository()
