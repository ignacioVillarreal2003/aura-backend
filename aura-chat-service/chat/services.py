"""Business-logic layer.

ChatService   — chat CRUD (synchronous; used by DRF views).
MessageService — message send + list/get/delete.
  * send_message()       — synchronous, used by the regular POST endpoint.
  * send_message_async() — async, used by the SSE streaming endpoint.
"""

from django.utils import timezone

from .models import Chat, ChatMembership, ChatMessage, SenderType, MembershipStatus
from .repositories import ChatRepository, MessageRepository
from .llm_client import llm_client
from .exceptions import ConversationNotFoundError, MessageNotFoundError, ForbiddenError

chat_repo = ChatRepository()
msg_repo = MessageRepository()

# Number of historical messages sent to the LLM per request.
_LLM_HISTORY_WINDOW = 4


class ChatService:
    def create_chat(self, data, user_id):
        chat = chat_repo.create(
            name=data["name"],
            created_by=user_id,
            system_prompt=data.get("system_prompt"),
            response_style=data.get("response_style"),
        )
        chat_repo.create_membership(chat.id, user_id, user_id)
        for member_id in data.get("member_ids", []):
            if member_id != user_id:
                chat_repo.create_membership(chat.id, member_id, user_id)
        return chat_repo.get_by_id(chat.id)

    def list_chats(self, user_id, limit=20):
        return chat_repo.get_chats_by_member(user_id, limit)

    def get_chat(self, chat_id, user_id):
        chat = chat_repo.get_by_id(chat_id)
        if not chat:
            raise ConversationNotFoundError()
        if not chat_repo.get_membership(chat_id, user_id):
            raise ForbiddenError()
        return chat

    def update_chat(self, chat_id, data, user_id):
        chat = self.get_chat(chat_id, user_id)
        return chat_repo.update(
            chat,
            name=data.get("name"),
            system_prompt=data.get("system_prompt"),
            response_style=data.get("response_style"),
            updated_by=user_id,
        )

    def delete_chat(self, chat_id, user_id):
        chat = self.get_chat(chat_id, user_id)
        chat_repo.soft_delete(chat, user_id)


class MessageService:
    # ------------------------------------------------------------------- sync

    def send_message(self, chat_id, message_text, user_id, token):
        """Synchronous send — used by POST /api/v1/chats/{id}/messages."""
        chat = chat_repo.get_by_id(chat_id)
        if not chat:
            raise ConversationNotFoundError()
        if not chat_repo.get_membership(chat_id, user_id):
            raise ForbiddenError()

        msg_repo.create(chat_id, message_text, SenderType.USER, created_by=user_id)

        history = msg_repo.get_by_chat(chat_id, limit=10_000)
        llm_messages = _build_llm_history(history)

        reply_text = llm_client.call_agent(llm_messages, token)
        reply_msg = msg_repo.create(chat_id, reply_text, SenderType.SYSTEM, created_by=None)
        chat_repo.update_last_message_at(chat)
        return reply_msg

    # ------------------------------------------------------------------ async

    async def send_message_async(self, chat_id: int, message_text: str, user_id: int, token: str) -> ChatMessage:
        """
        Async send — used by POST /api/v1/chats/{id}/messages/stream.

        All ORM calls use Django 4.2 native async methods (aget / acreate /
        asave) so the event loop is never blocked.
        """
        # --- validate chat & membership ---
        try:
            chat = await Chat.objects.aget(id=chat_id, deleted_at__isnull=True)
        except Chat.DoesNotExist:
            raise ConversationNotFoundError()

        membership_exists = await ChatMembership.objects.filter(
            chat_id=chat_id,
            member_id=user_id,
            deleted_at__isnull=True,
        ).aexists()
        if not membership_exists:
            raise ForbiddenError()

        # --- persist user message ---
        await ChatMessage.objects.acreate(
            chat_id=chat_id,
            message=message_text,
            sender_type=SenderType.USER,
            created_by=user_id,
        )

        # --- build history for LLM ---
        # Sliced querysets support async iteration in Django 4.2.
        # Cap at 10 000 to avoid unbounded memory usage on large chats.
        history = [
            msg
            async for msg in ChatMessage.objects.filter(
                chat_id=chat_id,
                deleted_at__isnull=True,
            ).order_by("created_at")[:10_000]
        ]
        llm_messages = _build_llm_history(history)

        # --- call LLM (non-blocking) ---
        reply_text = await llm_client.call_agent_async(llm_messages, token)

        # --- persist assistant reply ---
        reply_msg = await ChatMessage.objects.acreate(
            chat_id=chat_id,
            message=reply_text,
            sender_type=SenderType.SYSTEM,
            created_by=None,
        )

        # --- update last_message_at ---
        chat.last_message_at = timezone.now()
        await chat.asave(update_fields=["last_message_at"])

        return reply_msg

    # ----------------------------------------------------------------- other

    def list_messages(self, chat_id, user_id, limit=50, include_deleted=False):
        chat = chat_repo.get_by_id(chat_id)
        if not chat:
            raise ConversationNotFoundError()
        if not chat_repo.get_membership(chat_id, user_id):
            raise ForbiddenError()
        return msg_repo.get_by_chat(chat_id, limit, include_deleted)

    def get_message(self, chat_id, message_id, user_id):
        chat = chat_repo.get_by_id(chat_id)
        if not chat:
            raise ConversationNotFoundError()
        if not chat_repo.get_membership(chat_id, user_id):
            raise ForbiddenError()
        msg = msg_repo.get_by_id(message_id, chat_id)
        if not msg:
            raise MessageNotFoundError()
        return msg

    def delete_message(self, chat_id, message_id, user_id):
        msg = self.get_message(chat_id, message_id, user_id)
        msg_repo.soft_delete(msg, user_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_llm_history(messages) -> list[dict]:
    """Map chat messages to the LLM contract and apply the history window."""
    llm_messages = [
        {
            "role": "human" if m.sender_type == SenderType.USER else "assistant",
            "content": m.message,
        }
        for m in messages
    ]
    return llm_messages[-_LLM_HISTORY_WINDOW:]
