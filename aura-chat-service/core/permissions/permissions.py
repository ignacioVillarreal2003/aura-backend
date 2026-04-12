from rest_framework.permissions import BasePermission


class IsChatMember(BasePermission):
    """Allows access only to active members of the chat."""

    def has_permission(self, request, view):
        from apps.membership.models.chat_membership import ChatMembership

        chat_id = view.kwargs.get("chat_id") or view.kwargs.get("pk")
        if not chat_id:
            return False

        user = request.user
        if not hasattr(user, "id"):
            return False

        return ChatMembership.objects.filter(
            chat_id=chat_id,
            member_id=user.id,
            status="active",
        ).exists()


class IsChatOwner(BasePermission):
    """Allows access only to the creator (owner) of the chat."""

    def has_permission(self, request, view):
        from apps.chat.models.chat import Chat

        chat_id = view.kwargs.get("pk") or view.kwargs.get("chat_id")
        if not chat_id:
            return False

        user = request.user
        if not hasattr(user, "id"):
            return False

        return Chat.objects.filter(
            id=chat_id,
            created_by=user.id,
        ).exists()
