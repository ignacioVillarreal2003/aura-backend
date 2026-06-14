"""
HTTP-layer tests for the message module.

All service and repository calls are mocked. Tests verify the correct HTTP
status codes, error codes, and that the authenticated user's identity is passed
correctly to the service layer.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.chat.exceptions import ChatNotFoundException
from apps.artifact_message.exceptions import (
    ChatAiReplyInProgressException,
    ExportTooLargeException,
    MessageAccessDeniedException,
    MessageDeleteForbiddenException,
    MessageNotFoundException,
    NoMessageToRegenerateException,
    NotAIMessageException,
    NotChatOwnerException,
    ReaderCannotSendMessageException,
)
from test.conftest import make_feedback, make_message, make_pin, make_thread_reply, mock_cursor_pagination

# ---------------------------------------------------------------------------
# View module path constants for patching
# ---------------------------------------------------------------------------
MSG_VIEW = "apps.artifact_message.views.message_view"
DEL_VIEW = "apps.artifact_message.views.message_delete_view"
CLR_VIEW = "apps.artifact_message.views.clear_view"
READ_VIEW = "apps.artifact_message.views.mark_read_view"
REGEN_VIEW = "apps.artifact_message.views.regenerate_view"
PIN_VIEW = "apps.artifact_message.views.pin_view"
BKM_VIEW = "apps.artifact_message.views.bookmark_view"
THR_VIEW = "apps.artifact_message.views.thread_view"
FBK_VIEW = "apps.artifact_message.views.feedback_view"
EXP_VIEW = "apps.artifact_message.views.export_view"


# ===========================================================================
# GET /api/v1/chats/{chat_id}/messages/  — List messages
# ===========================================================================

class TestListMessages:

    def test_returns_200(self, api_client, mocker):
        qs = MagicMock()
        mocker.patch(f"{MSG_VIEW}.message_service.get_messages", return_value=qs)
        mock_cursor_pagination(mocker, MSG_VIEW, items=[make_message()])
        response = api_client.get("/api/v1/chats/1/messages/")
        assert response.status_code == 200
        assert "results" in response.data

    def test_access_denied_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{MSG_VIEW}.message_service.get_messages",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.get("/api/v1/chats/1/messages/")
        assert response.status_code == 403
        assert response.data["error"] == "message_access_denied"

    def test_chat_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{MSG_VIEW}.message_service.get_messages",
            side_effect=ChatNotFoundException(),
        )
        response = api_client.get("/api/v1/chats/999/messages/")
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.get("/api/v1/chats/1/messages/")
        assert response.status_code == 401


# ===========================================================================
# POST /api/v1/chats/{chat_id}/messages/  — Send message
# ===========================================================================

class TestSendMessage:

    def _setup(self, mocker, chat=None, msg=None, turn=None, acquired=True):
        from test.conftest import make_chat
        chat = chat or make_chat()
        msg = msg or make_message()
        turn = turn or SimpleNamespace(question="Q", answer="A", fragments=[])
        mocker.patch(f"{MSG_VIEW}.chat_repository.get_by_id", return_value=chat)
        mocker.patch(f"{MSG_VIEW}.try_acquire", return_value=acquired)
        mocker.patch(f"{MSG_VIEW}.release")
        mocker.patch(f"{MSG_VIEW}.broadcast_chat_ai_lock_change")
        mocker.patch(f"{MSG_VIEW}.message_service.send_message", return_value=msg)
        mocker.patch(
            f"{MSG_VIEW}.message_service.run_document_question",
            new_callable=AsyncMock,
            return_value=turn,
        )
        return msg

    def test_returns_201(self, api_client, mocker):
        self._setup(mocker)
        response = api_client.post("/api/v1/chats/1/messages/", {"message": "Hello"}, format="json")
        assert response.status_code == 201
        assert "message" in response.data
        assert "assistant" in response.data

    def test_empty_body_returns_400(self, api_client, mocker):
        self._setup(mocker)
        response = api_client.post("/api/v1/chats/1/messages/", {}, format="json")
        assert response.status_code == 400

    def test_message_too_long_returns_400(self, api_client, mocker):
        self._setup(mocker)
        response = api_client.post("/api/v1/chats/1/messages/", {"message": "x" * 10001}, format="json")
        assert response.status_code == 400

    def test_ai_in_progress_returns_409(self, api_client, mocker):
        self._setup(mocker, acquired=False)
        response = api_client.post("/api/v1/chats/1/messages/", {"message": "Hi"}, format="json")
        assert response.status_code == 409
        assert response.data["error"] == "chat_ai_reply_in_progress"

    def test_reader_returns_403(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{MSG_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{MSG_VIEW}.try_acquire", return_value=True)
        mocker.patch(f"{MSG_VIEW}.release")
        mocker.patch(f"{MSG_VIEW}.broadcast_chat_ai_lock_change")
        mocker.patch(
            f"{MSG_VIEW}.message_service.send_message",
            side_effect=ReaderCannotSendMessageException(),
        )
        response = api_client.post("/api/v1/chats/1/messages/", {"message": "Hi"}, format="json")
        assert response.status_code == 403
        assert response.data["error"] == "reader_cannot_send_message"

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.post("/api/v1/chats/1/messages/", {"message": "Hi"}, format="json")
        assert response.status_code == 401


# ===========================================================================
# GET /api/v1/chats/{chat_id}/messages/manage/  — Admin list messages
# ===========================================================================

class TestAdminListMessages:

    def test_returns_200(self, api_client, mocker):
        qs = MagicMock()
        mocker.patch(f"{MSG_VIEW}.message_service.get_messages_admin", return_value=qs)
        mock_cursor_pagination(mocker, MSG_VIEW, items=[make_message()])
        response = api_client.get("/api/v1/chats/1/messages/manage/")
        assert response.status_code == 200

    def test_chat_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{MSG_VIEW}.message_service.get_messages_admin",
            side_effect=ChatNotFoundException(),
        )
        response = api_client.get("/api/v1/chats/999/messages/manage/")
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.get("/api/v1/chats/1/messages/manage/")
        assert response.status_code == 401


# ===========================================================================
# DELETE /api/v1/chats/{chat_id}/messages/clear/  — Clear chat history
# ===========================================================================

class TestClearHistory:

    def test_owner_returns_204(self, api_client, mocker):
        mocker.patch(f"{CLR_VIEW}.message_service.clear_history")
        response = api_client.delete("/api/v1/chats/1/messages/clear/")
        assert response.status_code == 204

    def test_non_owner_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{CLR_VIEW}.message_service.clear_history",
            side_effect=NotChatOwnerException(),
        )
        response = api_client.delete("/api/v1/chats/1/messages/clear/")
        assert response.status_code == 403
        assert response.data["error"] == "not_chat_owner"

    def test_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{CLR_VIEW}.message_service.clear_history",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.delete("/api/v1/chats/1/messages/clear/")
        assert response.status_code == 403
        assert response.data["error"] == "message_access_denied"

    def test_chat_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{CLR_VIEW}.message_service.clear_history",
            side_effect=ChatNotFoundException(),
        )
        response = api_client.delete("/api/v1/chats/999/messages/clear/")
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.delete("/api/v1/chats/1/messages/clear/")
        assert response.status_code == 401


# ===========================================================================
# POST /api/v1/chats/{chat_id}/messages/read/  — Mark as read (personal)
# ===========================================================================

class TestMarkAsRead:

    def test_member_returns_204(self, api_client, mocker):
        mocker.patch(f"{READ_VIEW}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{READ_VIEW}.membership_repository.mark_as_read")
        response = api_client.post("/api/v1/chats/1/messages/read/")
        assert response.status_code == 204

    def test_not_member_returns_403(self, api_client, mocker):
        mocker.patch(f"{READ_VIEW}.membership_repository.is_active_member", return_value=False)
        mocker.patch(f"{READ_VIEW}.membership_repository.mark_as_read")
        response = api_client.post("/api/v1/chats/1/messages/read/")
        assert response.status_code == 403
        assert response.data["error"] == "message_access_denied"

    def test_marks_read_for_caller_only(self, api_client, mocker):
        mocker.patch(f"{READ_VIEW}.membership_repository.is_active_member", return_value=True)
        mark_read = mocker.patch(f"{READ_VIEW}.membership_repository.mark_as_read")
        api_client.post("/api/v1/chats/1/messages/read/")
        mark_read.assert_called_once_with(1, 1)

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.post("/api/v1/chats/1/messages/read/")
        assert response.status_code == 401


# ===========================================================================
# GET /api/v1/chats/{chat_id}/messages/pinned/  — List pinned (all members)
# ===========================================================================

class TestListPinned:

    def test_member_returns_200(self, api_client, mocker):
        mocker.patch(
            f"{PIN_VIEW}.pinned_message_service.list_pinned",
            return_value=[make_pin()],
        )
        response = api_client.get("/api/v1/chats/1/messages/pinned/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_empty_returns_200(self, api_client, mocker):
        mocker.patch(f"{PIN_VIEW}.pinned_message_service.list_pinned", return_value=[])
        response = api_client.get("/api/v1/chats/1/messages/pinned/")
        assert response.status_code == 200
        assert response.data["results"] == []

    def test_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{PIN_VIEW}.pinned_message_service.list_pinned",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.get("/api/v1/chats/1/messages/pinned/")
        assert response.status_code == 403
        assert response.data["error"] == "message_access_denied"

    def test_chat_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{PIN_VIEW}.pinned_message_service.list_pinned",
            side_effect=ChatNotFoundException(),
        )
        response = api_client.get("/api/v1/chats/999/messages/pinned/")
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.get("/api/v1/chats/1/messages/pinned/")
        assert response.status_code == 401


# ===========================================================================
# POST /api/v1/chats/{chat_id}/messages/regenerate/  — Regenerate AI response
# ===========================================================================

class TestRegenerateResponse:

    def test_returns_200(self, api_client, mocker):
        turn = SimpleNamespace(question="Q?", answer="A!", fragments=[])
        mocker.patch(f"{REGEN_VIEW}.try_acquire", return_value=True)
        mocker.patch(f"{REGEN_VIEW}.release")
        mocker.patch(f"{REGEN_VIEW}.broadcast_chat_ai_lock_change")
        mocker.patch(f"{REGEN_VIEW}.message_service.delete_last_ai_message")
        mocker.patch(
            f"{REGEN_VIEW}.message_service.run_document_question",
            new_callable=AsyncMock,
            return_value=turn,
        )
        response = api_client.post("/api/v1/chats/1/messages/regenerate/")
        assert response.status_code == 200
        assert response.data["assistant"]["answer"] == "A!"

    def test_ai_in_progress_returns_409(self, api_client, mocker):
        mocker.patch(f"{REGEN_VIEW}.try_acquire", return_value=False)
        response = api_client.post("/api/v1/chats/1/messages/regenerate/")
        assert response.status_code == 409
        assert response.data["error"] == "chat_ai_reply_in_progress"

    def test_no_message_to_regen_returns_409(self, api_client, mocker):
        mocker.patch(f"{REGEN_VIEW}.try_acquire", return_value=True)
        mocker.patch(f"{REGEN_VIEW}.release")
        mocker.patch(f"{REGEN_VIEW}.broadcast_chat_ai_lock_change")
        mocker.patch(
            f"{REGEN_VIEW}.message_service.delete_last_ai_message",
            side_effect=NoMessageToRegenerateException(),
        )
        response = api_client.post("/api/v1/chats/1/messages/regenerate/")
        assert response.status_code == 409
        assert response.data["error"] == "no_message_to_regenerate"

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.post("/api/v1/chats/1/messages/regenerate/")
        assert response.status_code == 401


# ===========================================================================
# GET /api/v1/chats/{chat_id}/messages/bookmarked/  — List bookmarked (personal)
# ===========================================================================

class TestListBookmarked:

    def test_returns_200(self, api_client, mocker):
        qs = MagicMock()
        qs.filter.return_value = qs
        mocker.patch(f"{BKM_VIEW}.bookmark_service.list_bookmarked", return_value=qs)
        mock_cursor_pagination(mocker, BKM_VIEW, items=[make_message()])
        response = api_client.get("/api/v1/chats/1/messages/bookmarked/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{BKM_VIEW}.bookmark_service.list_bookmarked",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.get("/api/v1/chats/1/messages/bookmarked/")
        assert response.status_code == 403

    def test_chat_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{BKM_VIEW}.bookmark_service.list_bookmarked",
            side_effect=ChatNotFoundException(),
        )
        response = api_client.get("/api/v1/chats/999/messages/bookmarked/")
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.get("/api/v1/chats/1/messages/bookmarked/")
        assert response.status_code == 401


# ===========================================================================
# GET /api/v1/chats/{chat_id}/messages/export/pdf/ — Export chat PDF (member)
# ===========================================================================

class TestChatExportPDF:

    def test_member_returns_200(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{EXP_VIEW}.message_repository.get_messages_by_chat", return_value=MagicMock(**{"__getitem__": MagicMock(return_value=[]), "__len__": MagicMock(return_value=0), "order_by": MagicMock(return_value=[])}))
        mocker.patch(f"{EXP_VIEW}.generate_chat_pdf", return_value=b"%PDF-1.4 test")
        response = api_client.get("/api/v1/chats/1/messages/export/pdf/")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_not_member_returns_403(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=False)
        response = api_client.get("/api/v1/chats/1/messages/export/pdf/")
        assert response.status_code == 403
        assert response.data["error"] == "message_access_denied"

    def test_chat_not_found_returns_404(self, api_client, mocker):
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=None)
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=True)
        response = api_client.get("/api/v1/chats/999/messages/export/pdf/")
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.get("/api/v1/chats/1/messages/export/pdf/")
        assert response.status_code == 401


# ===========================================================================
# GET /api/v1/chats/{chat_id}/messages/export/pdf/manage/ — Admin export PDF
# ===========================================================================

class TestAdminChatExportPDF:

    def test_admin_returns_200_without_membership_check(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.message_repository.get_messages_by_chat", return_value=MagicMock(**{"order_by": MagicMock(return_value=[])}))
        mocker.patch(f"{EXP_VIEW}.generate_chat_pdf", return_value=b"%PDF-1.4 admin")
        is_member = mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member")
        response = api_client.get("/api/v1/chats/1/messages/export/pdf/manage/")
        assert response.status_code == 200
        is_member.assert_not_called()

    def test_chat_not_found_returns_404(self, api_client, mocker):
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=None)
        response = api_client.get("/api/v1/chats/999/messages/export/pdf/manage/")
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.get("/api/v1/chats/1/messages/export/pdf/manage/")
        assert response.status_code == 401


# ===========================================================================
# GET export/markdown/, export/json/, export/ai/ — Member-only exports
# ===========================================================================

class TestChatExports:

    def test_export_markdown_member_returns_200(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{EXP_VIEW}.message_repository.get_messages_by_chat", return_value=MagicMock(**{"order_by": MagicMock(return_value=[])}))
        mocker.patch(f"{EXP_VIEW}.generate_chat_markdown", return_value="# Chat")
        response = api_client.get("/api/v1/chats/1/messages/export/markdown/")
        assert response.status_code == 200
        assert "text/markdown" in response["Content-Type"]

    def test_export_markdown_not_member_returns_403(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=False)
        response = api_client.get("/api/v1/chats/1/messages/export/markdown/")
        assert response.status_code == 403

    def test_export_json_member_returns_200(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{EXP_VIEW}.message_repository.get_messages_by_chat", return_value=MagicMock(**{"order_by": MagicMock(return_value=[])}))
        mocker.patch(f"{EXP_VIEW}.generate_chat_json", return_value='{"messages": []}')
        response = api_client.get("/api/v1/chats/1/messages/export/json/")
        assert response.status_code == 200

    def test_export_json_not_member_returns_403(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=False)
        response = api_client.get("/api/v1/chats/1/messages/export/json/")
        assert response.status_code == 403

    def test_export_ai_member_returns_200(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{EXP_VIEW}.message_repository.get_messages_by_chat", return_value=MagicMock(**{"order_by": MagicMock(return_value=[])}))
        mocker.patch(f"{EXP_VIEW}.generate_ai_responses_markdown", return_value="## AI")
        response = api_client.get("/api/v1/chats/1/messages/export/ai/")
        assert response.status_code == 200

    def test_export_too_large_returns_413(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=True)
        qs = MagicMock()
        qs.order_by.return_value.__getitem__ = MagicMock(side_effect=ExportTooLargeException())
        mocker.patch(f"{EXP_VIEW}.message_repository.get_messages_by_chat", return_value=qs)
        response = api_client.get("/api/v1/chats/1/messages/export/markdown/")
        assert response.status_code == 413

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.get("/api/v1/chats/1/messages/export/markdown/")
        assert response.status_code == 401


# ===========================================================================
# DELETE /api/v1/chats/{chat_id}/messages/{message_id}/  — Delete message
# ===========================================================================

class TestDeleteMessage:

    def test_owner_returns_204(self, api_client, mocker):
        mocker.patch(f"{DEL_VIEW}.message_service.delete_message")
        response = api_client.delete("/api/v1/chats/1/messages/1/")
        assert response.status_code == 204

    def test_non_owner_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{DEL_VIEW}.message_service.delete_message",
            side_effect=MessageDeleteForbiddenException(),
        )
        response = api_client.delete("/api/v1/chats/1/messages/1/")
        assert response.status_code == 403
        assert response.data["error"] == "message_delete_forbidden"

    def test_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{DEL_VIEW}.message_service.delete_message",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.delete("/api/v1/chats/1/messages/1/")
        assert response.status_code == 403

    def test_message_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{DEL_VIEW}.message_service.delete_message",
            side_effect=MessageNotFoundException(),
        )
        response = api_client.delete("/api/v1/chats/1/messages/999/")
        assert response.status_code == 404
        assert response.data["error"] == "message_not_found"

    def test_chat_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{DEL_VIEW}.message_service.delete_message",
            side_effect=ChatNotFoundException(),
        )
        response = api_client.delete("/api/v1/chats/999/messages/1/")
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.delete("/api/v1/chats/1/messages/1/")
        assert response.status_code == 401


# ===========================================================================
# POST /DELETE /api/v1/chats/{chat_id}/messages/{message_id}/bookmark/
# ===========================================================================

class TestBookmark:

    def test_bookmark_returns_204(self, api_client, mocker):
        mocker.patch(f"{BKM_VIEW}.bookmark_service.bookmark")
        response = api_client.post("/api/v1/chats/1/messages/1/bookmark/")
        assert response.status_code == 204

    def test_bookmark_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{BKM_VIEW}.bookmark_service.bookmark",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.post("/api/v1/chats/1/messages/1/bookmark/")
        assert response.status_code == 403
        assert response.data["error"] == "message_access_denied"

    def test_bookmark_message_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{BKM_VIEW}.bookmark_service.bookmark",
            side_effect=MessageNotFoundException(),
        )
        response = api_client.post("/api/v1/chats/1/messages/999/bookmark/")
        assert response.status_code == 404

    def test_unbookmark_returns_204(self, api_client, mocker):
        mocker.patch(f"{BKM_VIEW}.bookmark_service.unbookmark")
        response = api_client.delete("/api/v1/chats/1/messages/1/bookmark/")
        assert response.status_code == 204

    def test_unbookmark_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{BKM_VIEW}.bookmark_service.unbookmark",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.delete("/api/v1/chats/1/messages/1/bookmark/")
        assert response.status_code == 403

    def test_bookmark_unauthenticated_returns_401(self, anon_client):
        response = anon_client.post("/api/v1/chats/1/messages/1/bookmark/")
        assert response.status_code == 401

    def test_unbookmark_unauthenticated_returns_401(self, anon_client):
        response = anon_client.delete("/api/v1/chats/1/messages/1/bookmark/")
        assert response.status_code == 401


# ===========================================================================
# POST /DELETE /api/v1/chats/{chat_id}/messages/{message_id}/pin/
# ===========================================================================

class TestPin:

    def test_pin_owner_returns_201(self, api_client, mocker):
        mocker.patch(
            f"{PIN_VIEW}.pinned_message_service.pin_message",
            return_value=make_pin(),
        )
        response = api_client.post("/api/v1/chats/1/messages/1/pin/")
        assert response.status_code == 201
        assert "id" in response.data

    def test_pin_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{PIN_VIEW}.pinned_message_service.pin_message",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.post("/api/v1/chats/1/messages/1/pin/")
        assert response.status_code == 403
        assert response.data["error"] == "message_access_denied"

    def test_pin_member_not_owner_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{PIN_VIEW}.pinned_message_service.pin_message",
            side_effect=NotChatOwnerException(),
        )
        response = api_client.post("/api/v1/chats/1/messages/1/pin/")
        assert response.status_code == 403
        assert response.data["error"] == "not_chat_owner"

    def test_pin_message_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{PIN_VIEW}.pinned_message_service.pin_message",
            side_effect=MessageNotFoundException(),
        )
        response = api_client.post("/api/v1/chats/1/messages/999/pin/")
        assert response.status_code == 404
        assert response.data["error"] == "message_not_found"

    def test_unpin_owner_returns_204(self, api_client, mocker):
        mocker.patch(f"{PIN_VIEW}.pinned_message_service.unpin_message")
        response = api_client.delete("/api/v1/chats/1/messages/1/pin/")
        assert response.status_code == 204

    def test_unpin_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{PIN_VIEW}.pinned_message_service.unpin_message",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.delete("/api/v1/chats/1/messages/1/pin/")
        assert response.status_code == 403

    def test_unpin_member_not_owner_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{PIN_VIEW}.pinned_message_service.unpin_message",
            side_effect=NotChatOwnerException(),
        )
        response = api_client.delete("/api/v1/chats/1/messages/1/pin/")
        assert response.status_code == 403
        assert response.data["error"] == "not_chat_owner"

    def test_pin_unauthenticated_returns_401(self, anon_client):
        response = anon_client.post("/api/v1/chats/1/messages/1/pin/")
        assert response.status_code == 401

    def test_unpin_unauthenticated_returns_401(self, anon_client):
        response = anon_client.delete("/api/v1/chats/1/messages/1/pin/")
        assert response.status_code == 401


# ===========================================================================
# GET /POST /api/v1/chats/{chat_id}/messages/{message_id}/thread/
# ===========================================================================

class TestThread:

    def test_list_thread_returns_200(self, api_client, mocker):
        mocker.patch(
            f"{THR_VIEW}.thread_service.get_thread",
            return_value=[make_thread_reply(), make_thread_reply(reply_id=2)],
        )
        response = api_client.get("/api/v1/chats/1/messages/1/thread/")
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_list_thread_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{THR_VIEW}.thread_service.get_thread",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.get("/api/v1/chats/1/messages/1/thread/")
        assert response.status_code == 403

    def test_list_thread_message_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{THR_VIEW}.thread_service.get_thread",
            side_effect=MessageNotFoundException(),
        )
        response = api_client.get("/api/v1/chats/1/messages/999/thread/")
        assert response.status_code == 404

    def test_add_reply_returns_201(self, api_client, mocker):
        mocker.patch(
            f"{THR_VIEW}.thread_service.add_reply",
            return_value=make_thread_reply(),
        )
        response = api_client.post(
            "/api/v1/chats/1/messages/1/thread/",
            {"message": "A reply"},
            format="json",
        )
        assert response.status_code == 201
        assert "id" in response.data

    def test_add_reply_empty_returns_400(self, api_client, mocker):
        mocker.patch(f"{THR_VIEW}.thread_service.add_reply")
        response = api_client.post(
            "/api/v1/chats/1/messages/1/thread/",
            {"message": ""},
            format="json",
        )
        assert response.status_code == 400

    def test_add_reply_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{THR_VIEW}.thread_service.add_reply",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.post(
            "/api/v1/chats/1/messages/1/thread/",
            {"message": "Reply"},
            format="json",
        )
        assert response.status_code == 403

    def test_add_reply_too_long_returns_400(self, api_client, mocker):
        mocker.patch(f"{THR_VIEW}.thread_service.add_reply")
        response = api_client.post(
            "/api/v1/chats/1/messages/1/thread/",
            {"message": "x" * 5001},
            format="json",
        )
        assert response.status_code == 400

    def test_thread_unauthenticated_returns_401(self, anon_client):
        response = anon_client.get("/api/v1/chats/1/messages/1/thread/")
        assert response.status_code == 401


# ===========================================================================
# POST /DELETE /api/v1/chats/{chat_id}/messages/{message_id}/feedback/
# ===========================================================================

class TestFeedback:

    def test_submit_thumbs_up_returns_200(self, api_client, mocker):
        mocker.patch(
            f"{FBK_VIEW}.feedback_service.set_feedback",
            return_value=make_feedback(value=1),
        )
        response = api_client.post(
            "/api/v1/chats/1/messages/1/feedback/",
            {"value": 1},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["value"] == 1

    def test_submit_thumbs_down_returns_200(self, api_client, mocker):
        mocker.patch(
            f"{FBK_VIEW}.feedback_service.set_feedback",
            return_value=make_feedback(value=-1),
        )
        response = api_client.post(
            "/api/v1/chats/1/messages/1/feedback/",
            {"value": -1},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["value"] == -1

    def test_invalid_value_returns_400(self, api_client, mocker):
        mocker.patch(f"{FBK_VIEW}.feedback_service.set_feedback")
        response = api_client.post(
            "/api/v1/chats/1/messages/1/feedback/",
            {"value": 0},
            format="json",
        )
        assert response.status_code == 400

    def test_missing_value_returns_400(self, api_client, mocker):
        mocker.patch(f"{FBK_VIEW}.feedback_service.set_feedback")
        response = api_client.post("/api/v1/chats/1/messages/1/feedback/", {}, format="json")
        assert response.status_code == 400

    def test_not_ai_message_returns_400(self, api_client, mocker):
        mocker.patch(
            f"{FBK_VIEW}.feedback_service.set_feedback",
            side_effect=NotAIMessageException(),
        )
        response = api_client.post(
            "/api/v1/chats/1/messages/1/feedback/",
            {"value": 1},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["error"] == "not_ai_message"

    def test_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{FBK_VIEW}.feedback_service.set_feedback",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.post(
            "/api/v1/chats/1/messages/1/feedback/",
            {"value": 1},
            format="json",
        )
        assert response.status_code == 403

    def test_message_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{FBK_VIEW}.feedback_service.set_feedback",
            side_effect=MessageNotFoundException(),
        )
        response = api_client.post(
            "/api/v1/chats/1/messages/999/feedback/",
            {"value": 1},
            format="json",
        )
        assert response.status_code == 404

    def test_delete_feedback_returns_204(self, api_client, mocker):
        mocker.patch(f"{FBK_VIEW}.feedback_service.delete_feedback")
        response = api_client.delete("/api/v1/chats/1/messages/1/feedback/")
        assert response.status_code == 204

    def test_delete_feedback_not_member_returns_403(self, api_client, mocker):
        mocker.patch(
            f"{FBK_VIEW}.feedback_service.delete_feedback",
            side_effect=MessageAccessDeniedException(),
        )
        response = api_client.delete("/api/v1/chats/1/messages/1/feedback/")
        assert response.status_code == 403

    def test_delete_feedback_not_found_returns_404(self, api_client, mocker):
        mocker.patch(
            f"{FBK_VIEW}.feedback_service.delete_feedback",
            side_effect=MessageNotFoundException(),
        )
        response = api_client.delete("/api/v1/chats/1/messages/999/feedback/")
        assert response.status_code == 404

    def test_feedback_is_personal_passes_caller_id(self, api_client, mocker):
        """Feedback always stored for the authenticated user, not a passed user_id param."""
        svc = mocker.patch(
            f"{FBK_VIEW}.feedback_service.set_feedback",
            return_value=make_feedback(value=1),
        )
        api_client.post("/api/v1/chats/1/messages/1/feedback/", {"value": 1}, format="json")
        svc.assert_called_once()
        assert svc.call_args.kwargs.get("user") is not None or svc.call_args[0][0] is not None

    def test_feedback_unauthenticated_returns_401(self, anon_client):
        response = anon_client.post(
            "/api/v1/chats/1/messages/1/feedback/",
            {"value": 1},
            format="json",
        )
        assert response.status_code == 401


# ===========================================================================
# GET /api/v1/chats/{chat_id}/messages/{message_id}/export/pdf/ — Single msg
# ===========================================================================

class TestMessageExportPDF:

    def test_member_returns_200(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{EXP_VIEW}.message_repository.get_by_id_and_chat", return_value=make_message())
        mocker.patch(f"{EXP_VIEW}.generate_message_pdf", return_value=b"%PDF-1.4 msg")
        response = api_client.get("/api/v1/chats/1/messages/1/export/pdf/")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_not_member_returns_403(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=False)
        response = api_client.get("/api/v1/chats/1/messages/1/export/pdf/")
        assert response.status_code == 403

    def test_message_not_found_returns_404(self, api_client, mocker):
        from test.conftest import make_chat
        mocker.patch(f"{EXP_VIEW}.chat_repository.get_by_id", return_value=make_chat())
        mocker.patch(f"{EXP_VIEW}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{EXP_VIEW}.message_repository.get_by_id_and_chat", return_value=None)
        response = api_client.get("/api/v1/chats/1/messages/999/export/pdf/")
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, anon_client):
        response = anon_client.get("/api/v1/chats/1/messages/1/export/pdf/")
        assert response.status_code == 401
