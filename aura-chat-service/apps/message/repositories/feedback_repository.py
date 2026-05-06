from django.utils import timezone

from apps.message.models.message_feedback import MessageFeedback


class FeedbackRepository:
    @staticmethod
    def set(message_id: int, user_id: int, value: int) -> MessageFeedback:
        obj = MessageFeedback.objects.filter(message_id=message_id, user_id=user_id).first()
        if obj is None:
            return MessageFeedback.objects.create(
                message_id=message_id,
                user_id=user_id,
                value=value,
            )
        obj.value = value
        obj.updated_at = timezone.now()
        obj.save(update_fields=["value", "updated_at"])
        return obj

    @staticmethod
    def delete(message_id: int, user_id: int) -> bool:
        deleted, _ = MessageFeedback.objects.filter(
            message_id=message_id, user_id=user_id
        ).delete()
        return deleted > 0

    @staticmethod
    def get(message_id: int, user_id: int) -> MessageFeedback | None:
        return MessageFeedback.objects.filter(message_id=message_id, user_id=user_id).first()


feedback_repository = FeedbackRepository()
