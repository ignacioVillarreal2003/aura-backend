"""
Service-layer unit tests for the message module.

All dependencies (repositories, LLM client, channel layer) are mocked so tests
run without a database or external services.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.chat.exceptions import ChatNotFoundException
from apps.artifact_message.exceptions import (
    ChatLockedException,
    MessageAccessDeniedException,
    MessageDeleteForbiddenException,
    MessageNotFoundException,
    NotAIMessageException,
    NotChatOwnerException,
    LLMServiceException,
    ReaderCannotSendMessageException,
)
from apps.artifact.exceptions import (
    TranscriptionBusyException,
    TranscriptionException,
)
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import AgentRunResult, DocumentQuestionResult, GeneralChatResult
from core.clients.transcription_client import TranscriptionBusyError
from apps.artifact.services.artifact_bookmark_service import BookmarkService
from apps.artifact.services.artifact_feedback_service import FeedbackService
from apps.artifact_message.services.message_service import ChatAIMode, MessageService
from apps.artifact.services.artifact_pin_service import PinService
from apps.artifact.services.artifact_thread_service import ThreadService
from test.conftest import make_artifact, make_chat, make_message, make_pin, make_user, make_feedback, make_thread_reply

# ---------------------------------------------------------------------------
# Module path constants used for patching
# ---------------------------------------------------------------------------
MSG_SVC = "apps.artifact_message.services.message_service"
PIN_SVC = "apps.artifact.services.artifact_pin_service"
BKM_SVC = "apps.artifact.services.artifact_bookmark_service"
FBK_SVC = "apps.artifact.services.artifact_feedback_service"
THR_SVC = "apps.artifact.services.artifact_thread_service"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_atomic(mocker):
    """Prevent @transaction.atomic from touching the database in unit tests."""
    mocker.patch("django.db.transaction.Atomic.__enter__", return_value=None)
    mocker.patch("django.db.transaction.Atomic.__exit__", return_value=False)
    mocker.patch(f"{MSG_SVC}.transaction.on_commit", side_effect=lambda fn: None)


def _user(user_id=1):
    return make_user(user_id=user_id)


def _chat(created_by=1, is_locked=False):
    return make_chat(created_by=created_by, is_locked=is_locked)


def _msg(msg_id=1, chat_id=1, created_by=1, sender_type="user"):
    m = make_message(msg_id=msg_id, chat_id=chat_id, created_by=created_by, sender_type=sender_type)
    m.delete = MagicMock()
    return m


# ===========================================================================
# MessageService
# ===========================================================================

class TestMessageServiceRunDocumentQuestion:

    def _patch_access_ok(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)

    @pytest.mark.asyncio
    async def test_saves_ai_message_when_answer_present(self, mocker):
        self._patch_access_ok(mocker)
        mocker.patch(f"{MSG_SVC}.message_repository.get_recent_messages", return_value=[])
        result = DocumentQuestionResult(question="q", answer="respuesta", fragments=[{"x": 1}])
        mocker.patch(f"{MSG_SVC}.llm_client.document_question", new_callable=AsyncMock, return_value=result)
        ai_msg = _msg(msg_id=7, sender_type="assistant")
        save = mocker.patch.object(MessageService, "_save_ai_message", return_value=ai_msg)
        out = await MessageService().run_document_question(_user(), chat_id=1)
        assert out.answer == "respuesta"
        assert out.assistant_message is ai_msg
        save.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_answer_skips_save(self, mocker):
        self._patch_access_ok(mocker)
        mocker.patch(f"{MSG_SVC}.message_repository.get_recent_messages", return_value=[])
        result = DocumentQuestionResult(question="q", answer="   ", fragments=[])
        mocker.patch(f"{MSG_SVC}.llm_client.document_question", new_callable=AsyncMock, return_value=result)
        save = mocker.patch.object(MessageService, "_save_ai_message")
        out = await MessageService().run_document_question(_user(), chat_id=1)
        assert out.assistant_message is None
        save.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_http_error_raises_502(self, mocker):
        self._patch_access_ok(mocker)
        mocker.patch(f"{MSG_SVC}.message_repository.get_recent_messages", return_value=[])
        mocker.patch(
            f"{MSG_SVC}.llm_client.document_question",
            new_callable=AsyncMock,
            side_effect=HttpClientException("boom", status_code=500),
        )
        with pytest.raises(LLMServiceException):
            await MessageService().run_document_question(_user(), chat_id=1)

    @pytest.mark.asyncio
    async def test_non_member_raises_access_denied(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=False)
        with pytest.raises(MessageAccessDeniedException):
            await MessageService().run_document_question(_user(), chat_id=1)

    @pytest.mark.asyncio
    async def test_builds_history_with_role_mapping(self, mocker):
        self._patch_access_ok(mocker)
        m_user = _msg(msg_id=1, sender_type="user")
        m_user.message = "pregunta"
        m_ai = _msg(msg_id=2, sender_type="assistant")
        m_ai.message = "respuesta"
        mocker.patch(f"{MSG_SVC}.message_repository.get_recent_messages", return_value=[m_user, m_ai])
        llm = mocker.patch(
            f"{MSG_SVC}.llm_client.document_question",
            new_callable=AsyncMock,
            return_value=DocumentQuestionResult(question="q", answer="", fragments=[]),
        )
        await MessageService().run_document_question(_user(), chat_id=1)
        args, _ = llm.call_args
        history = args[0]
        roles = {h["content"]: h["role"] for h in history}
        assert roles["pregunta"] == "human"       # USER → human
        assert roles["respuesta"] == "assistant"  # SYSTEM → assistant

    @pytest.mark.asyncio
    async def test_no_regen_feedback_leaves_history_unchanged(self, mocker):
        self._patch_access_ok(mocker)
        m_user = _msg(msg_id=1, sender_type="user")
        m_user.message = "pregunta"
        mocker.patch(f"{MSG_SVC}.message_repository.get_recent_messages", return_value=[m_user])
        llm = mocker.patch(
            f"{MSG_SVC}.llm_client.document_question",
            new_callable=AsyncMock,
            return_value=DocumentQuestionResult(question="q", answer="", fragments=[]),
        )
        await MessageService().run_document_question(_user(), chat_id=1)
        history = llm.call_args[0][0]
        assert len(history) == 1
        assert history[0]["content"] == "pregunta"


class TestMessageServiceSendMessage:

    def test_send_message_happy_path(self, mocker):
        _patch_atomic(mocker)
        user = _user()
        chat = _chat()
        msg = _msg()
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=chat)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.membership_repository.get_role", return_value="editor")
        mocker.patch(f"{MSG_SVC}.message_repository.create", return_value=msg)
        mocker.patch(f"{MSG_SVC}.chat_repository.touch_last_message_at")
        mocker.patch(f"{MSG_SVC}._broadcast_user_message_to_chat_group")

        svc = MessageService()
        result = svc.send_message(user, chat_id=1, text="Hello")

        assert result is msg

    def test_send_message_chat_not_found_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=None)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)

        svc = MessageService()
        with pytest.raises(ChatNotFoundException):
            svc.send_message(_user(), chat_id=99, text="Hi")

    def test_send_message_not_member_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.get_role", return_value=None)

        svc = MessageService()
        with pytest.raises(MessageAccessDeniedException):
            svc.send_message(_user(), chat_id=1, text="Hi")

    def test_send_message_reader_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.membership_repository.get_role", return_value="reader")

        svc = MessageService()
        with pytest.raises(ReaderCannotSendMessageException):
            svc.send_message(_user(), chat_id=1, text="Hi")

    def test_send_message_locked_chat_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat(is_locked=True))
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.membership_repository.get_role", return_value="editor")

        svc = MessageService()
        with pytest.raises(ChatLockedException):
            svc.send_message(_user(), chat_id=1, text="Hi")


class TestMessageServiceGetMessages:

    def test_get_messages_happy_path(self, mocker):
        qs = MagicMock()
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_messages_by_chat", return_value=qs)

        svc = MessageService()
        result = svc.get_messages(_user(), chat_id=1)

        assert result is qs

    def test_get_messages_access_denied_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=False)

        svc = MessageService()
        with pytest.raises(MessageAccessDeniedException):
            svc.get_messages(_user(), chat_id=1)

    def test_get_messages_chat_not_found_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=None)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)

        svc = MessageService()
        with pytest.raises(ChatNotFoundException):
            svc.get_messages(_user(), chat_id=99)


class TestMessageServiceGetMessagesAdmin:

    def test_get_messages_admin_happy_path(self, mocker):
        qs = MagicMock()
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.message_repository.get_messages_by_chat", return_value=qs)

        svc = MessageService()
        result = svc.get_messages_admin(_user(), chat_id=1)

        assert result is qs

    def test_get_messages_admin_chat_not_found_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=None)

        svc = MessageService()
        with pytest.raises(ChatNotFoundException):
            svc.get_messages_admin(_user(), chat_id=99)


class TestMessageServiceDeleteMessage:

    def test_delete_message_owner_succeeds(self, mocker):
        msg = _msg()
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_by_id_and_chat", return_value=msg)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_chat_owner", return_value=True)

        svc = MessageService()
        svc.delete_message(_user(), chat_id=1, message_id=1)

        msg.delete.assert_called_once_with(deleted_by=1)

    def test_delete_message_non_owner_raises(self, mocker):
        msg = _msg()
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_by_id_and_chat", return_value=msg)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_chat_owner", return_value=False)

        svc = MessageService()
        with pytest.raises(MessageDeleteForbiddenException):
            svc.delete_message(_user(user_id=2), chat_id=1, message_id=1)

    def test_delete_message_author_non_owner_raises(self, mocker):
        """Message author without owner role cannot delete — owner-only rule."""
        user = _user(user_id=5)
        msg = _msg(created_by=5)
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_by_id_and_chat", return_value=msg)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_chat_owner", return_value=False)

        svc = MessageService()
        with pytest.raises(MessageDeleteForbiddenException):
            svc.delete_message(user, chat_id=1, message_id=1)

    def test_delete_message_not_found_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_by_id_and_chat", return_value=None)

        svc = MessageService()
        with pytest.raises(MessageNotFoundException):
            svc.delete_message(_user(), chat_id=1, message_id=999)

    def test_delete_message_not_member_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=False)

        svc = MessageService()
        with pytest.raises(MessageAccessDeniedException):
            svc.delete_message(_user(user_id=99), chat_id=1, message_id=1)


class TestChatAIMode:

    def test_normalize_accepts_known_modes(self):
        for mode in ("document_question", "general_chat", "rag_agent", "agent"):
            assert ChatAIMode.normalize(mode) == mode

    def test_normalize_defaults_on_unknown_or_missing(self):
        assert ChatAIMode.normalize("bogus") == ChatAIMode.DOCUMENT_QUESTION
        assert ChatAIMode.normalize(None) == ChatAIMode.DOCUMENT_QUESTION
        assert ChatAIMode.normalize(123) == ChatAIMode.DOCUMENT_QUESTION


class TestMessageServiceCompleteExtractors:

    def test_document_question_extractor_prefers_result_then_fallbacks(self):
        q, a, f = MessageService._extract_document_question_complete(
            {"question": " q ", "answer": " a ", "fragments": [{"id": 1}]},
            "acc", "lastq", [{"id": 9}],
        )
        assert (q, a, f) == ("q", "a", [{"id": 1}])

    def test_document_question_extractor_uses_fallbacks_when_empty(self):
        q, a, f = MessageService._extract_document_question_complete(
            {}, "  accumulated ", "fallback-q", [{"id": 9}],
        )
        assert q == "fallback-q"
        assert a == "accumulated"
        assert f == [{"id": 9}]

    def test_general_chat_extractor_never_returns_fragments(self):
        q, a, f = MessageService._extract_general_chat_complete(
            {"answer": " hola "}, "acc", "", [],
        )
        assert (q, a, f) == ("", "hola", [])

    def test_general_chat_extractor_falls_back_to_accumulated(self):
        q, a, f = MessageService._extract_general_chat_complete(
            {"answer": "   "}, "  streamed ", "", [],
        )
        assert a == "streamed"

    def test_agent_extractor_takes_last_assistant_message(self):
        result = {
            "messages": [
                {"role": "human", "content": "hi"},
                {"role": "assistant", "content": "first"},
                {"role": "assistant", "content": "  final  "},
            ],
            "fragments": [{"id": 3}],
        }
        q, a, f = MessageService._extract_agent_complete(result, "acc", "", [])
        assert (q, a, f) == ("", "final", [{"id": 3}])

    def test_agent_extractor_falls_back_to_accumulated(self):
        q, a, f = MessageService._extract_agent_complete(
            {"messages": [{"role": "human", "content": "hi"}]}, "  acc ", "", [{"id": 1}],
        )
        assert a == "acc"
        assert f == [{"id": 1}]


class TestMessageServiceRunAIModes:

    def _patch_access_ok(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_recent_messages", return_value=[])

    @pytest.mark.asyncio
    async def test_run_general_chat_saves_answer(self, mocker):
        self._patch_access_ok(mocker)
        mocker.patch(
            f"{MSG_SVC}.llm_client.general_chat",
            new_callable=AsyncMock,
            return_value=GeneralChatResult(answer="hola", messages=[]),
        )
        ai_msg = _msg(msg_id=11, sender_type="assistant")
        save = mocker.patch.object(MessageService, "_save_ai_message", return_value=ai_msg)
        out = await MessageService().run_general_chat(_user(), chat_id=1)
        assert out.answer == "hola"
        assert out.fragments == []
        assert out.assistant_message is ai_msg
        save.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_general_chat_forwards_system_prompt(self, mocker):
        mocker.patch(
            f"{MSG_SVC}.chat_repository.get_by_id",
            return_value=make_chat(system_prompt="be terse"),
        )
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_recent_messages", return_value=[])
        llm = mocker.patch(
            f"{MSG_SVC}.llm_client.general_chat",
            new_callable=AsyncMock,
            return_value=GeneralChatResult(answer="", messages=[]),
        )
        await MessageService().run_general_chat(_user(), chat_id=1)
        assert llm.call_args.kwargs["system_prompt"] == "be terse"

    @pytest.mark.asyncio
    async def test_run_rag_agent_saves_with_fragments(self, mocker):
        self._patch_access_ok(mocker)
        mocker.patch(
            f"{MSG_SVC}.llm_client.rag_agent",
            new_callable=AsyncMock,
            return_value=AgentRunResult(answer="resp", messages=[], fragments=[{"id": 5}]),
        )
        ai_msg = _msg(msg_id=12, sender_type="assistant")
        save = mocker.patch.object(MessageService, "_save_ai_message", return_value=ai_msg)
        out = await MessageService().run_rag_agent(_user(), chat_id=1)
        assert out.answer == "resp"
        assert out.fragments == [{"id": 5}]
        save.assert_called_once_with(1, 1, "resp", [{"id": 5}])

    @pytest.mark.asyncio
    async def test_run_general_chat_http_error_raises_llm_exception(self, mocker):
        self._patch_access_ok(mocker)
        mocker.patch(
            f"{MSG_SVC}.llm_client.general_chat",
            new_callable=AsyncMock,
            side_effect=HttpClientException("boom", status_code=503),
        )
        with pytest.raises(LLMServiceException):
            await MessageService().run_general_chat(_user(), chat_id=1)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mode,target",
        [
            (ChatAIMode.DOCUMENT_QUESTION, "run_document_question"),
            (ChatAIMode.GENERAL_CHAT, "run_general_chat"),
            (ChatAIMode.RAG_AGENT, "run_rag_agent"),
        ],
    )
    async def test_run_ai_reply_dispatches_by_mode(self, mocker, mode, target):
        expected = DocumentQuestionResult(question="", answer="x", fragments=[])
        dispatched = mocker.patch.object(
            MessageService, target, new_callable=AsyncMock, return_value=expected
        )
        out = await MessageService().run_ai_reply(mode, _user(), chat_id=1)
        assert out is expected
        dispatched.assert_called_once()

# ===========================================================================
# PinService
# ===========================================================================

class TestPinService:

    def test_list_pinned_happy_path(self, mocker):
        pin = make_pin()
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.pinned_message_repository.list_by_chat", return_value=[pin])

        svc = PinService()
        result = svc.list_pinned(_user(), chat_id=1)

        assert result == [pin]

    def test_list_pinned_not_member_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=False)

        svc = PinService()
        with pytest.raises(MessageAccessDeniedException):
            svc.list_pinned(_user(), chat_id=1)

    def test_pin_message_owner_succeeds(self, mocker):
        pin = make_pin()
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.membership_repository.is_chat_owner", return_value=True)
        mocker.patch(f"{PIN_SVC}.artifact_repository.get_by_id", return_value=make_artifact(source_chat_id=1))
        mocker.patch(f"{PIN_SVC}.pinned_message_repository.pin", return_value=(pin, True))

        svc = PinService()
        result = svc.pin_message(_user(), chat_id=1, artifact_id=1)

        assert result is pin

    def test_pin_message_not_member_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=False)

        svc = PinService()
        with pytest.raises(MessageAccessDeniedException):
            svc.pin_message(_user(), chat_id=1, artifact_id=1)

    def test_pin_message_member_not_owner_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.membership_repository.is_chat_owner", return_value=False)

        svc = PinService()
        with pytest.raises(NotChatOwnerException):
            svc.pin_message(_user(user_id=2), chat_id=1, artifact_id=1)

    def test_pin_message_not_found_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.membership_repository.is_chat_owner", return_value=True)
        mocker.patch(f"{PIN_SVC}.artifact_repository.get_by_id", return_value=None)

        svc = PinService()
        with pytest.raises(MessageNotFoundException):
            svc.pin_message(_user(), chat_id=1, artifact_id=999)

    def test_unpin_message_owner_succeeds(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.membership_repository.is_chat_owner", return_value=True)
        unpin = mocker.patch(f"{PIN_SVC}.pinned_message_repository.unpin")

        svc = PinService()
        svc.unpin_message(_user(), chat_id=1, artifact_id=1)

        unpin.assert_called_once_with(1, 1)

    def test_unpin_message_not_member_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=False)

        svc = PinService()
        with pytest.raises(MessageAccessDeniedException):
            svc.unpin_message(_user(), chat_id=1, artifact_id=1)

    def test_unpin_message_member_not_owner_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.membership_repository.is_chat_owner", return_value=False)

        svc = PinService()
        with pytest.raises(NotChatOwnerException):
            svc.unpin_message(_user(user_id=2), chat_id=1, artifact_id=1)


# ===========================================================================
# BookmarkService
# ===========================================================================

class TestBookmarkService:

    def test_bookmark_happy_path(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.artifact_repository.get_by_id", return_value=make_artifact(source_chat_id=1))
        create = mocker.patch(f"{BKM_SVC}.bookmark_repository.create")

        svc = BookmarkService()
        svc.bookmark(_user(), chat_id=1, artifact_id=1)

        create.assert_called_once_with(artifact_id=1, user_id=1)

    def test_bookmark_not_member_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=False)

        svc = BookmarkService()
        with pytest.raises(MessageAccessDeniedException):
            svc.bookmark(_user(), chat_id=1, artifact_id=1)

    def test_bookmark_message_not_found_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.artifact_repository.get_by_id", return_value=None)

        svc = BookmarkService()
        with pytest.raises(MessageNotFoundException):
            svc.bookmark(_user(), chat_id=1, artifact_id=999)

    def test_unbookmark_happy_path(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.artifact_repository.get_by_id", return_value=make_artifact(source_chat_id=1))
        delete = mocker.patch(f"{BKM_SVC}.bookmark_repository.delete")

        svc = BookmarkService()
        svc.unbookmark(_user(), chat_id=1, artifact_id=1)

        delete.assert_called_once_with(artifact_id=1, user_id=1)

    def test_unbookmark_not_member_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=False)

        svc = BookmarkService()
        with pytest.raises(MessageAccessDeniedException):
            svc.unbookmark(_user(), chat_id=1, artifact_id=1)

    def test_unbookmark_message_not_found_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.artifact_repository.get_by_id", return_value=None)

        svc = BookmarkService()
        with pytest.raises(MessageNotFoundException):
            svc.unbookmark(_user(), chat_id=1, artifact_id=999)

    def test_list_bookmarked_happy_path(self, mocker):
        qs = MagicMock()
        qs.filter.return_value = qs
        mocker.patch(f"{BKM_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.bookmark_repository.get_bookmarked_artifact_ids", return_value=[1, 2])
        mocker.patch(f"{BKM_SVC}.message_repository.get_messages_by_chat", return_value=qs)

        svc = BookmarkService()
        result = svc.list_bookmarked(_user(), chat_id=1)

        assert result is qs.filter.return_value

    def test_list_bookmarked_chat_not_found_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.chat_repository.get_by_id", return_value=None)

        svc = BookmarkService()
        with pytest.raises(ChatNotFoundException):
            svc.list_bookmarked(_user(), chat_id=99)

    def test_list_bookmarked_not_member_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=False)

        svc = BookmarkService()
        with pytest.raises(MessageAccessDeniedException):
            svc.list_bookmarked(_user(), chat_id=1)

    def test_bookmark_is_personal_uses_caller_user_id(self, mocker):
        """Bookmarks always stored under the authenticated user's id, never another user's."""
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.artifact_repository.get_by_id", return_value=make_artifact(source_chat_id=1))
        create = mocker.patch(f"{BKM_SVC}.bookmark_repository.create")

        user = _user(user_id=42)
        svc = BookmarkService()
        svc.bookmark(user, chat_id=1, artifact_id=1)

        create.assert_called_once_with(artifact_id=1, user_id=42)


# ===========================================================================
# FeedbackService
# ===========================================================================

class TestFeedbackService:

    def _ai_artifact(self, sender_type="assistant"):
        """Return an artifact SimpleNamespace whose message_content has the given sender_type."""
        artifact = make_artifact(source_chat_id=1)
        artifact.message_content = SimpleNamespace(sender_type=sender_type)
        return artifact

    def test_set_feedback_happy_path(self, mocker):
        fb = make_feedback(value=1)
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.artifact_repository.get_by_id", return_value=self._ai_artifact("system"))
        mocker.patch(f"{FBK_SVC}.feedback_repository.set", return_value=fb)

        svc = FeedbackService()
        result = svc.set_feedback(_user(), chat_id=1, artifact_id=1, value=1)

        assert result.value == 1

    def test_set_feedback_not_member_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=False)

        svc = FeedbackService()
        with pytest.raises(MessageAccessDeniedException):
            svc.set_feedback(_user(), chat_id=1, artifact_id=1, value=1)

    def test_set_feedback_message_not_found_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.artifact_repository.get_by_id", return_value=None)

        svc = FeedbackService()
        with pytest.raises(MessageNotFoundException):
            svc.set_feedback(_user(), chat_id=1, artifact_id=999, value=1)

    def test_set_feedback_not_ai_message_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.artifact_repository.get_by_id", return_value=self._ai_artifact("user"))

        svc = FeedbackService()
        with pytest.raises(NotAIMessageException):
            svc.set_feedback(_user(), chat_id=1, artifact_id=1, value=1)

    def test_set_feedback_thumbs_down(self, mocker):
        fb = make_feedback(value=-1)
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.artifact_repository.get_by_id", return_value=self._ai_artifact("system"))
        mocker.patch(f"{FBK_SVC}.feedback_repository.set", return_value=fb)

        svc = FeedbackService()
        result = svc.set_feedback(_user(), chat_id=1, artifact_id=1, value=-1)

        assert result.value == -1

    def test_set_feedback_is_personal_uses_caller_user_id(self, mocker):
        """Feedback is always stored under the authenticated user's id."""
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.artifact_repository.get_by_id", return_value=self._ai_artifact("system"))
        repo_set = mocker.patch(f"{FBK_SVC}.feedback_repository.set", return_value=make_feedback(value=1))

        user = _user(user_id=77)
        svc = FeedbackService()
        svc.set_feedback(user, chat_id=1, artifact_id=1, value=1)

        repo_set.assert_called_once_with(artifact_id=1, user_id=77, value=1, reason=None, comment=None)

    def test_delete_feedback_happy_path(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.artifact_repository.get_by_id", return_value=self._ai_artifact("system"))
        repo_del = mocker.patch(f"{FBK_SVC}.feedback_repository.delete")

        svc = FeedbackService()
        svc.delete_feedback(_user(), chat_id=1, artifact_id=1)

        repo_del.assert_called_once_with(artifact_id=1, user_id=1)

    def test_delete_feedback_not_member_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=False)

        svc = FeedbackService()
        with pytest.raises(MessageAccessDeniedException):
            svc.delete_feedback(_user(), chat_id=1, artifact_id=1)

    def test_delete_feedback_message_not_found_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.artifact_repository.get_by_id", return_value=None)

        svc = FeedbackService()
        with pytest.raises(MessageNotFoundException):
            svc.delete_feedback(_user(), chat_id=1, artifact_id=999)

    def test_delete_feedback_not_ai_message_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.artifact_repository.get_by_id", return_value=self._ai_artifact("user"))

        svc = FeedbackService()
        with pytest.raises(NotAIMessageException):
            svc.delete_feedback(_user(), chat_id=1, artifact_id=1)


# ===========================================================================
# ThreadService
# ===========================================================================

class TestThreadService:

    def test_get_thread_happy_path(self, mocker):
        replies = [make_thread_reply(), make_thread_reply(reply_id=2)]
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{THR_SVC}.artifact_repository.get_by_id", return_value=make_artifact(source_chat_id=1))
        mocker.patch(f"{THR_SVC}.thread_repository.get_by_artifact", return_value=replies)

        svc = ThreadService()
        result = svc.get_thread(_user(), chat_id=1, artifact_id=1)

        assert result == replies

    def test_get_thread_not_member_raises(self, mocker):
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=False)

        svc = ThreadService()
        with pytest.raises(MessageAccessDeniedException):
            svc.get_thread(_user(), chat_id=1, artifact_id=1)

    def test_get_thread_message_not_found_raises(self, mocker):
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{THR_SVC}.artifact_repository.get_by_id", return_value=None)

        svc = ThreadService()
        with pytest.raises(MessageNotFoundException):
            svc.get_thread(_user(), chat_id=1, artifact_id=999)

    def test_add_reply_happy_path(self, mocker):
        reply = make_thread_reply()
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{THR_SVC}.artifact_repository.get_by_id", return_value=make_artifact(source_chat_id=1))
        mocker.patch(f"{THR_SVC}.thread_repository.create", return_value=reply)

        svc = ThreadService()
        result = svc.add_reply(_user(), chat_id=1, artifact_id=1, message_text="A reply")

        assert result is reply

    def test_add_reply_passes_correct_args(self, mocker):
        reply = make_thread_reply()
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{THR_SVC}.artifact_repository.get_by_id", return_value=make_artifact(source_chat_id=1))
        create = mocker.patch(f"{THR_SVC}.thread_repository.create", return_value=reply)

        user = _user(user_id=5)
        svc = ThreadService()
        svc.add_reply(user, chat_id=1, artifact_id=1, message_text="My reply")

        create.assert_called_once_with(
            parent_artifact_id=1,
            message="My reply",
            created_by=5,
        )

    def test_add_reply_not_member_raises(self, mocker):
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=False)

        svc = ThreadService()
        with pytest.raises(MessageAccessDeniedException):
            svc.add_reply(_user(), chat_id=1, artifact_id=1, message_text="Reply")

    def test_add_reply_message_not_found_raises(self, mocker):
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{THR_SVC}.artifact_repository.get_by_id", return_value=None)

        svc = ThreadService()
        with pytest.raises(MessageNotFoundException):
            svc.add_reply(_user(), chat_id=1, artifact_id=999, message_text="Reply")
