from django.utils import timezone
from .models import Chat, ChatMembership, ChatMessage, SenderType, MembershipStatus


class ChatRepository:
    def create(self, name, created_by, system_prompt=None, response_style=None):
        return Chat.objects.create(
            name=name,
            created_by=created_by,
            system_prompt=system_prompt,
            response_style=response_style,
        )

    def get_by_id(self, chat_id):
        try:
            return (
                Chat.objects
                .prefetch_related('memberships', 'messages')
                .get(id=chat_id, deleted_at__isnull=True)
            )
        except Chat.DoesNotExist:
            return None

    def get_chats_by_member(self, member_id, limit=20):
        return list(
            Chat.objects
            .filter(
                memberships__member_id=member_id,
                memberships__deleted_at__isnull=True,
                deleted_at__isnull=True,
            )
            .prefetch_related('memberships')
            .order_by('-created_at')[:limit]
        )

    def update(self, chat, name=None, system_prompt=None, response_style=None, updated_by=None):
        if name is not None:
            chat.name = name
        if system_prompt is not None:
            chat.system_prompt = system_prompt
        if response_style is not None:
            chat.response_style = response_style
        chat.updated_by = updated_by
        chat.updated_at = timezone.now()
        chat.save()
        return chat

    def soft_delete(self, chat, deleted_by):
        chat.soft_delete(deleted_by)

    def create_membership(self, chat_id, member_id, created_by):
        return ChatMembership.objects.create(
            chat_id=chat_id,
            member_id=member_id,
            created_by=created_by,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
        )

    def get_membership(self, chat_id, member_id):
        try:
            return ChatMembership.objects.get(
                chat_id=chat_id,
                member_id=member_id,
                deleted_at__isnull=True,
            )
        except ChatMembership.DoesNotExist:
            return None

    def update_last_message_at(self, chat):
        chat.last_message_at = timezone.now()
        chat.save(update_fields=['last_message_at'])


class MessageRepository:
    def create(self, chat_id, message, sender_type, created_by=None):
        return ChatMessage.objects.create(
            chat_id=chat_id,
            message=message,
            sender_type=sender_type,
            created_by=created_by,
        )

    def get_by_id(self, message_id, chat_id=None):
        try:
            filters = {'id': message_id, 'deleted_at__isnull': True}
            if chat_id is not None:
                filters['chat_id'] = chat_id
            return ChatMessage.objects.get(**filters)
        except ChatMessage.DoesNotExist:
            return None

    def get_by_chat(self, chat_id, limit=100, include_deleted=False):
        qs = ChatMessage.objects.filter(chat_id=chat_id)
        if not include_deleted:
            qs = qs.filter(deleted_at__isnull=True)
        return list(qs.order_by('created_at')[:limit])

    def soft_delete(self, msg, deleted_by):
        msg.soft_delete(deleted_by)
