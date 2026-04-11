from .models import SenderType
from .repositories import ChatRepository, MessageRepository
from .llm_client import llm_client
from .exceptions import ConversationNotFoundError, MessageNotFoundError, ForbiddenError

chat_repo = ChatRepository()
msg_repo = MessageRepository()


class ChatService:
    def create_chat(self, data, user_id):
        chat = chat_repo.create(
            name=data['name'],
            created_by=user_id,
            system_prompt=data.get('system_prompt'),
            response_style=data.get('response_style'),
        )
        chat_repo.create_membership(chat.id, user_id, user_id)
        for member_id in data.get('member_ids', []):
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
            name=data.get('name'),
            system_prompt=data.get('system_prompt'),
            response_style=data.get('response_style'),
            updated_by=user_id,
        )

    def delete_chat(self, chat_id, user_id):
        chat = self.get_chat(chat_id, user_id)
        chat_repo.soft_delete(chat, user_id)


class MessageService:
    def send_message(self, chat_id, message_text, user_id, token):
        chat = chat_repo.get_by_id(chat_id)
        if not chat:
            raise ConversationNotFoundError()
        if not chat_repo.get_membership(chat_id, user_id):
            raise ForbiddenError()

        msg_repo.create(chat_id, message_text, SenderType.USER, created_by=user_id)

        history = msg_repo.get_by_chat(chat_id, limit=10000)
        llm_messages = [
            {'role': 'human' if m.sender_type == SenderType.USER else 'assistant', 'content': m.message}
            for m in history
        ]
        llm_messages = llm_messages[-4:]

        reply_text = llm_client.call_agent(llm_messages, token)
        reply_msg = msg_repo.create(chat_id, reply_text, SenderType.SYSTEM, created_by=None)
        chat_repo.update_last_message_at(chat)

        return reply_msg

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
