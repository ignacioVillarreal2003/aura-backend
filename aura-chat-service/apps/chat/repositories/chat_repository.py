import logging

from django.db.models import Count, Q, QuerySet

from apps.chat.models.chat import Chat

logger = logging.getLogger(__name__)


class ChatRepository:
    @staticmethod
    def create(name: str, created_by: int, **kwargs) -> Chat:
        return Chat.objects.create(name=name, created_by=created_by, **kwargs)

    @staticmethod
    def get_by_id(chat_id: int) -> Chat | None:
        try:
            return Chat.objects.get(pk=chat_id)
        except Chat.DoesNotExist:
            return None

    @staticmethod
    def get_chats_for_member(member_id: int) -> QuerySet[Chat]:
        return (
            Chat.objects
            .filter(
                chatmembership__member_id=member_id,
                chatmembership__status="active",
                chatmembership__deleted_at__isnull=True,
            )
            .annotate(
                member_count=Count(
                    "chatmembership",
                    filter=Q(
                        chatmembership__status="active",
                        chatmembership__deleted_at__isnull=True,
                    ),
                )
            )
            .distinct()
        )

    @staticmethod
    def get_chats_created_by(user_id: int) -> QuerySet[Chat]:
        return (
            Chat.objects
            .filter(created_by=user_id)
            .annotate(
                member_count=Count(
                    "chatmembership",
                    filter=Q(
                        chatmembership__status="active",
                        chatmembership__deleted_at__isnull=True,
                    ),
                )
            )
        )

    @staticmethod
    def update(chat: Chat, updated_by: int, **fields) -> Chat:
        from django.utils import timezone

        for key, value in fields.items():
            setattr(chat, key, value)
        chat.updated_by = updated_by
        chat.updated_at = timezone.now()

        update_fields = list(fields.keys()) + ["updated_by", "updated_at"]
        chat.save(update_fields=update_fields)
        return chat

    @staticmethod
    def soft_delete(chat: Chat, deleted_by: int) -> None:
        chat.delete(deleted_by=deleted_by)


chat_repository = ChatRepository()
