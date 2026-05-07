from apps.message.models.message_bookmark import MessageBookmark


class BookmarkRepository:
    @staticmethod
    def create(message_id: int, user_id: int) -> MessageBookmark:
        obj, _ = MessageBookmark.objects.get_or_create(message_id=message_id, user_id=user_id)
        return obj

    @staticmethod
    def delete(message_id: int, user_id: int) -> bool:
        deleted, _ = MessageBookmark.objects.filter(
            message_id=message_id, user_id=user_id
        ).delete()
        return deleted > 0

    @staticmethod
    def get_bookmarked_message_ids(chat_id: int, user_id: int) -> list[int]:
        from apps.message.models.chat_message import ChatMessage

        return list(
            MessageBookmark.objects.filter(
                user_id=user_id,
                message__chat_id=chat_id,
            ).values_list("message_id", flat=True)
        )


bookmark_repository = BookmarkRepository()
