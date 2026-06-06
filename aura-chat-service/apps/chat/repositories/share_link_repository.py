import uuid
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.chat.models.chat_share_link import ChatShareLink


class ShareLinkRepository:
    @staticmethod
    def create(chat_id: int, created_by: int, expires_at=None) -> ChatShareLink:
        return ChatShareLink.objects.create(
            chat_id=chat_id,
            created_by=created_by,
            expires_at=expires_at,
        )

    @staticmethod
    def get_by_id(link_id: int, chat_id: int) -> ChatShareLink | None:
        try:
            return ChatShareLink.objects.get(pk=link_id, chat_id=chat_id)
        except ChatShareLink.DoesNotExist:
            return None

    @staticmethod
    def get_by_token(token: uuid.UUID) -> ChatShareLink | None:
        try:
            return ChatShareLink.objects.select_related("chat").get(token=token)
        except ChatShareLink.DoesNotExist:
            return None

    @staticmethod
    def list_by_chat(chat_id: int, active_only: bool = True) -> QuerySet[ChatShareLink]:
        qs = ChatShareLink.objects.filter(chat_id=chat_id)
        if active_only:
            now = timezone.now()
            qs = qs.filter(
                is_active=True,
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now)
            )
        return qs.order_by("-created_at")

    @staticmethod
    def deactivate(link: ChatShareLink) -> ChatShareLink:
        link.is_active = False
        link.save(update_fields=["is_active"])
        return link

    @staticmethod
    def deactivate_by_chat(chat_id: int) -> None:
        ChatShareLink.objects.filter(chat_id=chat_id, is_active=True).update(is_active=False)


share_link_repository = ShareLinkRepository()
