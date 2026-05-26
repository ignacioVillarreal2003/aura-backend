import pytest

from apps.chat.services.chat_service import chat_service
from apps.membership.services.membership_service import membership_service
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.message_repository import message_repository
from core.authentication.authenticated_user import AuthenticatedUser


def make_user(id: int, **kwargs) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=id,
        email=f"user{id}@test.com",
        username=f"user{id}",
        permissions=("*",),
        **kwargs,
    )


@pytest.fixture(autouse=True)
def _silence_externals(mocker):
    mocker.patch("apps.membership.services.membership_service.notification_client.emit_event")
    mocker.patch("apps.chat.services.chat_service._broadcast_chat_locked_changed")
    mocker.patch("apps.message.services.message_service._broadcast_user_message_to_chat_group")
    mocker.patch("apps.message.services.message_service.broadcast_chat_ai_lock_change")


@pytest.fixture
def owner():
    return make_user(id=1000)


@pytest.fixture
def member_user():
    return make_user(id=1001)


@pytest.fixture
def other_user():
    return make_user(id=1002)


@pytest.fixture
def chat(owner):
    return chat_service.create_chat(owner, name="Integration Chat")


@pytest.fixture
def chat_with_member(chat, owner, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    return chat


@pytest.fixture
def user_message(chat, owner):
    return message_repository.create(
        chat_id=chat.id,
        message="Hello from integration test",
        sender_type=ChatMessage.SenderType.USER,
        created_by=owner.id,
    )


@pytest.fixture
def ai_message(chat, owner):
    return message_repository.create(
        chat_id=chat.id,
        message="AI response",
        sender_type=ChatMessage.SenderType.SYSTEM,
        created_by=owner.id,
    )
