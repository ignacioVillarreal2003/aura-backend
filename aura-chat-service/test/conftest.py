import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIClient

from core.authentication.authenticated_user import AuthenticatedUser


# ---------------------------------------------------------------------------
# Object factories
# ---------------------------------------------------------------------------

def make_user(user_id=1, permissions=("*",), roles=("owner",), email=None):
    return AuthenticatedUser(
        id=user_id,
        email=email or f"user{user_id}@example.com",
        username=f"user{user_id}",
        roles=tuple(roles),
        permissions=tuple(permissions),
    )


def make_chat(chat_id=1, created_by=1, **overrides):
    now = timezone.now()
    data = dict(
        id=chat_id,
        name="Test Chat",
        system_prompt=None,
        response_style=None,
        tags=[],
        is_locked=False,
        last_message_at=None,
        created_by=created_by,
        created_at=now,
        updated_by=None,
        updated_at=now,
        # Annotated fields for ChatListResponse
        member_count=1,
        unread_count=0,
        pinned_at=None,
        archived_at=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_message(msg_id=1, artifact_id=1, chat_id=1, created_by=1, sender_type="user", **overrides):
    now = timezone.now()
    artifact = make_artifact(artifact_id=artifact_id, source_chat_id=chat_id)
    data = dict(
        id=msg_id,
        artifact_id=artifact_id,
        artifact=artifact,
        message="Hello world",
        sender_type=sender_type,
        created_by=created_by,
        created_at=now,
        is_bookmarked=False,
        user_feedback=None,
        user_feedback_reason=None,
        user_feedback_comment=None,
        thread_reply_count=0,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_membership(member_id=2, chat_id=1, **overrides):
    now = timezone.now()
    data = dict(
        id=1,
        member_id=member_id,
        chat_id=chat_id,
        status="active",
        role="editor",
        joined_at=now,
        left_at=None,
        created_by=1,
        created_at=now,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_webhook(webhook_id=1, chat_id=1, created_by=1, **overrides):
    now = timezone.now()
    data = dict(
        id=webhook_id,
        chat_id=chat_id,
        url="https://example.com/webhook",
        events=["message.created"],
        is_active=True,
        secret="abc123secret",
        created_by=created_by,
        created_at=now,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_share_link(link_id=1, chat_id=1, created_by=1, **overrides):
    now = timezone.now()
    data = dict(
        id=link_id,
        chat_id=chat_id,
        token=uuid.uuid4(),
        created_by=created_by,
        created_at=now,
        expires_at=None,
        is_active=True,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_pin(pin_id=1, chat_id=1, artifact_id=1, **overrides):
    now = timezone.now()
    data = dict(
        id=pin_id,
        chat_id=chat_id,
        artifact_id=artifact_id,
        pinned_by=1,
        pinned_at=now,
        artifact=make_artifact(artifact_id=artifact_id, source_chat_id=chat_id),
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_checklist_item(item_id=1, text="Verificar equipo", position=0, is_checked=False, notes="", **overrides):
    data = dict(id=item_id, text=text, is_checked=is_checked, notes=notes, position=position)
    data.update(overrides)
    return SimpleNamespace(**data)


def make_checklist_section(sec_id=1, title="Preparación", position=0, items=None, **overrides):
    data = dict(
        id=sec_id,
        title=title,
        position=position,
        items=items if items is not None else [make_checklist_item()],
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_checklist(cl_id=1, title="Checklist de prueba", mode="direct",
                   retrieve_context=None, process_documents=None, document_ids=None,
                   source_chat_id=1, created_by=1, sections=None, **overrides):
    now = timezone.now()
    artifact = make_artifact(
        artifact_id=cl_id, type="CHECKLIST",
        retrieve_context=retrieve_context, process_documents=process_documents, document_ids=document_ids,
        source_chat_id=source_chat_id, created_by=created_by,
    )
    data = dict(
        id=cl_id,
        artifact_id=cl_id,
        artifact=artifact,
        title=title,
        description="",
        query="",
        sections=sections if sections is not None else [make_checklist_section()],
        item_count=1,
        checked_count=0,
        created_by=created_by,
        created_at=now,
        updated_by=None,
        updated_at=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_assistant(assistant_id=1, name="Asistente Alfa", description="Descripción",
                   system_prompt="Eres un asistente especializado.", response_style="",
                   avatar_emoji="🤖", is_active=True, **overrides):
    now = timezone.now()
    data = dict(
        id=assistant_id,
        name=name,
        description=description,
        system_prompt=system_prompt,
        response_style=response_style,
        avatar_emoji=avatar_emoji,
        is_active=is_active,
        created_by=1,
        created_at=now,
        updated_by=None,
        updated_at=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_report(report_id=1, title="Informe de prueba", report_type="SITREP",
                content="Contenido del informe", mode="direct",
                retrieve_context=None, process_documents=None, document_ids=None,
                source_chat_id=1, created_by=1, **overrides):
    now = timezone.now()
    # generation params / source_chat_id now live on the linked Artifact, not the report row.
    artifact = make_artifact(
        artifact_id=report_id, type="REPORT",
        retrieve_context=retrieve_context, process_documents=process_documents, document_ids=document_ids,
        source_chat_id=source_chat_id, created_by=created_by,
    )
    data = dict(
        id=report_id,
        artifact_id=report_id,
        artifact=artifact,
        type=report_type,
        title=title,
        description="",
        query="",
        content=content,
        created_by=created_by,
        created_at=now,
        updated_by=None,
        updated_at=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_artifact(artifact_id=1, type="REPORT", title="Artefacto de prueba",
                  description="", status="draft", version=1, mode="direct",
                  retrieve_context=None, process_documents=None, document_ids=None,
                  source_chat_id=1, created_by=1, fragments=None, **overrides):
    now = timezone.now()
    data = dict(
        id=artifact_id,
        type=type,
        title=title,
        description=description,
        status=status,
        version=version,
        retrieve_context=retrieve_context,
        process_documents=process_documents,
        document_ids=document_ids if document_ids is not None else [],
        source_chat_id=source_chat_id,
        fragments=fragments,
        created_by=created_by,
        created_at=now,
        updated_by=None,
        updated_at=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_artifact_version(version_id=1, artifact_id=1, version_number=1,
                          title="Artefacto de prueba", description="", status="draft",
                          mode="direct", change_summary="Versión inicial", created_by=1, **overrides):
    now = timezone.now()
    data = dict(
        id=version_id,
        artifact_id=artifact_id,
        version_number=version_number,
        title=title,
        description=description,
        status=status,
        mode=mode,
        change_summary=change_summary,
        created_by=created_by,
        created_at=now,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_message_artifact(link_id=1, position=0, artifact=None, **overrides):
    data = dict(
        id=link_id,
        position=position,
        artifact=artifact if artifact is not None else make_artifact(),
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_feedback(fb_id=1, artifact_id=1, user_id=1, value=1, reason=None, comment=None, **overrides):
    now = timezone.now()
    data = dict(
        id=fb_id,
        artifact_id=artifact_id,
        user_id=user_id,
        value=value,
        reason=reason,
        comment=comment,
        created_at=now,
        updated_at=now,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_thread_reply(reply_id=1, parent_artifact_id=1, **overrides):
    now = timezone.now()
    data = dict(
        id=reply_id,
        parent_artifact_id=parent_artifact_id,
        message="A reply message",
        created_by=1,
        created_at=now,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


# ---------------------------------------------------------------------------
# Pagination helpers
# ---------------------------------------------------------------------------

def mock_cursor_pagination(mocker, module_path, items=None):
    """Replaces MessageCursorPagination in a view module with a predictable mock."""
    items = items or []
    MockPager = mocker.patch(f"{module_path}.MessageCursorPagination")
    instance = MagicMock()
    instance.paginate_queryset.return_value = items
    instance.get_paginated_response.side_effect = lambda data: Response(
        {"next": None, "previous": None, "results": data}
    )
    MockPager.return_value = instance
    return instance


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user():
    return make_user()


@pytest.fixture
def mock_validate_token(mocker, user):
    return mocker.patch(
        "core.authentication.authentication_provider.authentication_provider.validate_token",
        return_value=user,
    )


@pytest.fixture
def api_client(mock_validate_token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer test_token")
    return client


@pytest.fixture
def anon_client():
    return APIClient()
