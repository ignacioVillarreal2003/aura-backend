from django.db.models import QuerySet

from apps.chat.models.webhook import ChatWebhook


class WebhookRepository:
    @staticmethod
    def create(chat_id: int, url: str, events: list[str], secret: str, created_by: int) -> ChatWebhook:
        return ChatWebhook.objects.create(
            chat_id=chat_id,
            url=url,
            events=events,
            secret=secret,
            created_by=created_by,
        )

    @staticmethod
    def get_by_id(webhook_id: int, chat_id: int) -> ChatWebhook | None:
        try:
            return ChatWebhook.objects.get(pk=webhook_id, chat_id=chat_id)
        except ChatWebhook.DoesNotExist:
            return None

    @staticmethod
    def list_by_chat(chat_id: int) -> QuerySet[ChatWebhook]:
        return ChatWebhook.objects.filter(chat_id=chat_id).order_by("-created_at")

    @staticmethod
    def list_active_by_chat_and_event(chat_id: int, event: str) -> list[ChatWebhook]:
        return list(
            ChatWebhook.objects.filter(
                chat_id=chat_id,
                is_active=True,
                events__contains=[event],
            )
        )

    @staticmethod
    def update(webhook: ChatWebhook, **fields) -> ChatWebhook:
        for key, value in fields.items():
            setattr(webhook, key, value)
        webhook.save(update_fields=list(fields.keys()))
        return webhook

    @staticmethod
    def delete(webhook: ChatWebhook) -> None:
        webhook.delete()


webhook_repository = WebhookRepository()
