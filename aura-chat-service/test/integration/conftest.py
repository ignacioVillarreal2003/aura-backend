import pytest
from django.db import connection

from apps.chat.services.chat_service import chat_service
from apps.membership.services.membership_service import membership_service
from apps.message.models.artifact_message import ArtifactMessage
from apps.message.repositories.message_repository import message_repository
from core.authentication.authenticated_user import AuthenticatedUser

def _get_unmanaged_models():
    from apps.artifact.models import (
        Artifact,
        ArtifactMessage,
        ArtifactVersion,
    )
    from apps.assistant.models import Assistant
    from apps.chat.models.chat import Chat
    from apps.chat.models.chat_share_link import ChatShareLink
    from apps.checklist.models import ArtifactChecklist, ArtifactChecklistItem, ArtifactChecklistSection
    from apps.decision_brief.models import DecisionBrief, DecisionBriefOption
    from apps.lessons_learned.models import ArtifactLessonsLearned, ArtifactLessonsLearnedItem
    from apps.membership.models.chat_membership import ChatMembership
    from apps.message.models.message_bookmark import ArtifactBookmark
    from apps.message.models.message_feedback import ArtifactFeedback
    from apps.message.models.message_thread_reply import ArtifactThreadReply
    from apps.message.models.pinned_message import ArtifactPin
    from apps.quiz.models import ArtifactQuiz, ArtifactQuizOption, ArtifactQuizQuestion
    from apps.report.models import ArtifactReport
    from apps.timeline.models import ArtifactTimeline, ArtifactTimelineEvent
    # Order matters: parent tables before child tables (FK dependencies)
    return [
        Chat, Assistant,
        Artifact, ArtifactVersion,
        ArtifactMessage, ChatMembership, ChatShareLink,
        ArtifactPin, ArtifactBookmark, ArtifactThreadReply, ArtifactFeedback,
        ArtifactReport,
        ArtifactChecklist, ArtifactChecklistSection, ArtifactChecklistItem,
        ArtifactQuiz, ArtifactQuizQuestion, ArtifactQuizOption,
        ArtifactTimeline, ArtifactTimelineEvent,
        ArtifactLessonsLearned, ArtifactLessonsLearnedItem,
        DecisionBrief, DecisionBriefOption,
    ]


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Create tables for all unmanaged models so integration tests can hit real DB rows."""
    models = _get_unmanaged_models()
    with django_db_blocker.unblock():
        for m in models:
            m._meta.managed = True
        with connection.schema_editor() as editor:
            for m in models:
                editor.create_model(m)
        for m in models:
            m._meta.managed = False


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
        sender_type=ArtifactMessage.SenderType.USER,
        created_by=owner.id,
    )


@pytest.fixture
def ai_message(chat, owner):
    return message_repository.create(
        chat_id=chat.id,
        message="AI response",
        sender_type=ArtifactMessage.SenderType.SYSTEM,
        created_by=owner.id,
    )
