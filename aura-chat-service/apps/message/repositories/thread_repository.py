from django.db.models import QuerySet

from apps.message.models.message_thread_reply import MessageThreadReply


class ThreadRepository:
    @staticmethod
    def get_by_message(parent_message_id: int) -> QuerySet[MessageThreadReply]:
        return MessageThreadReply.objects.filter(parent_message_id=parent_message_id)

    @staticmethod
    def create(parent_message_id: int, message: str, created_by: int) -> MessageThreadReply:
        return MessageThreadReply.objects.create(
            parent_message_id=parent_message_id,
            message=message,
            created_by=created_by,
        )


thread_repository = ThreadRepository()
