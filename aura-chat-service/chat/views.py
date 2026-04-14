"""Django views for the chat service.

Endpoints
---------
GET  /api/v1/chats                                   ChatListView
POST /api/v1/chats                                   ChatListView

GET  /api/v1/chats/<id>                              ChatDetailView
PATCH /api/v1/chats/<id>                             ChatDetailView
DELETE /api/v1/chats/<id>                            ChatDetailView

GET  /api/v1/chats/<id>/messages                     MessageListView
POST /api/v1/chats/<id>/messages                     MessageListView  (JSON response)

POST /api/v1/chats/<id>/messages/stream              SSEChatStreamView (SSE response)
  Accepts:  {"message": "<text>"}
  Streams:  text/event-stream
    event: start    — sent immediately; chat_id confirmed, processing started
    event: delta    — one text chunk of the assistant reply
    event: complete — message_id, finish_reason
    event: error    — code, message

GET  /api/v1/chats/<id>/messages/<msg_id>            MessageDetailView
DELETE /api/v1/chats/<id>/messages/<msg_id>          MessageDetailView
"""

import json
import logging

from django.conf import settings
from django.http import StreamingHttpResponse
from django.views import View
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import JWTAuthentication
from .exceptions import AppError
from .serializers import (
    ChatMessageSerializer,
    ChatSerializer,
    ChatSummarySerializer,
    CreateChatSerializer,
    SendMessageSerializer,
    UpdateChatSerializer,
)
from .services import ChatService, MessageService
from .sse import sse_complete, sse_delta, sse_error, sse_start
from .throttling import RateLimiter

logger = logging.getLogger(__name__)

_chat_service = ChatService()
_message_service = MessageService()
_rate_limiter = RateLimiter()
_authenticator = JWTAuthentication()

# ---------------------------------------------------------------------------
# Chat CRUD
# ---------------------------------------------------------------------------


class ChatListView(APIView):
    def get(self, request):
        limit = min(
            int(request.query_params.get("limit", settings.DEFAULT_PAGE_SIZE)),
            settings.MAX_PAGE_SIZE,
        )
        chats = _chat_service.list_chats(request.user.id, limit)
        data = ChatSummarySerializer(chats, many=True).data
        return Response({
            "data": data,
            "pagination": {"has_more": False, "next_cursor": None, "total_count": len(data)},
        })

    def post(self, request):
        serializer = CreateChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chat = _chat_service.create_chat(serializer.validated_data, request.user.id)
        return Response(ChatSerializer(chat).data, status=status.HTTP_201_CREATED)


class ChatDetailView(APIView):
    def get(self, request, chat_id):
        chat = _chat_service.get_chat(chat_id, request.user.id)
        return Response(ChatSerializer(chat).data)

    def patch(self, request, chat_id):
        serializer = UpdateChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chat = _chat_service.update_chat(chat_id, serializer.validated_data, request.user.id)
        return Response(ChatSerializer(chat).data)

    def delete(self, request, chat_id):
        _chat_service.delete_chat(chat_id, request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Message CRUD  (synchronous — returns full JSON response)
# ---------------------------------------------------------------------------


class MessageListView(APIView):
    def get(self, request, chat_id):
        limit = min(
            int(request.query_params.get("limit", 50)),
            settings.MAX_MESSAGES_PAGE_SIZE,
        )
        include_deleted = request.query_params.get("include_deleted", "false").lower() == "true"
        messages = _message_service.list_messages(chat_id, request.user.id, limit, include_deleted)
        data = ChatMessageSerializer(messages, many=True).data
        return Response({
            "data": data,
            "pagination": {"has_more": False, "next_cursor": None, "total_count": len(data)},
        })

    def post(self, request, chat_id):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = getattr(request, "bearer_token", "user_token_123")
        reply = _message_service.send_message(
            chat_id,
            serializer.validated_data["message"],
            request.user.id,
            token,
        )
        return Response(ChatMessageSerializer(reply).data, status=status.HTTP_201_CREATED)


class MessageDetailView(APIView):
    def get(self, request, chat_id, message_id):
        msg = _message_service.get_message(chat_id, message_id, request.user.id)
        return Response(ChatMessageSerializer(msg).data)

    def delete(self, request, chat_id, message_id):
        _message_service.delete_message(chat_id, message_id, request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# SSE streaming view
# ---------------------------------------------------------------------------


class SSEChatStreamView(View):
    """
    POST /api/v1/chats/<chat_id>/messages/stream

    Fully async view that accepts a chat message and returns the assistant
    reply as a Server-Sent Events stream.  Requires ASGI (Daphne) to work
    correctly — the event loop must not be blocked.

    Authentication is handled manually (JWTAuthentication) because Django's
    async View does not go through DRF's dispatch pipeline.

    Rate limiting: RATE_LIMIT_MESSAGES_PER_MINUTE per user (Redis-backed).
    """

    async def post(self, request, chat_id: int):
        # --- 1. authenticate ---
        user, token = await self._authenticate(request)
        if user is None:
            return self._sse_error_response(401, "UNAUTHORIZED", "Authentication required.")

        # --- 2. rate limit ---
        limit = getattr(settings, "RATE_LIMIT_MESSAGES_PER_MINUTE", 30)
        if not _rate_limiter.is_allowed(f"msg:{user.id}", limit=limit, window=60):
            return self._sse_error_response(429, "RATE_LIMITED", "Too many messages. Please slow down.")

        # --- 3. parse & validate body ---
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return self._sse_error_response(400, "INVALID_REQUEST", "Request body must be valid JSON.")

        message = body.get("message", "")
        if not isinstance(message, str):
            return self._sse_error_response(422, "VALIDATION_ERROR", "Field 'message' must be a string.")
        message = message.strip()
        if not message:
            return self._sse_error_response(422, "VALIDATION_ERROR", "Field 'message' is required and cannot be empty.")
        if len(message) > 100_000:
            return self._sse_error_response(422, "VALIDATION_ERROR", "Field 'message' exceeds maximum length of 100 000 characters.")

        # --- 4. stream ---
        response = StreamingHttpResponse(
            self._event_stream(chat_id, message, user.id, token),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"   # Disable Nginx/proxy response buffering
        response["Connection"] = "keep-alive"
        return response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _authenticate(self, request):
        """
        Calls the remote auth service asynchronously.

        Returns (MockUser, token) on success, (None, None) on failure.
        """
        try:
            result = await _authenticator.authenticate_async(request)
            if result is None:
                return None, None
            user, token = result
            bearer = getattr(request, "bearer_token", token or "user_token_123")
            return user, bearer
        except Exception:
            return None, None

    @staticmethod
    def _sse_error_response(http_status: int, code: str, message: str) -> StreamingHttpResponse:
        """Return an SSE-framed error before streaming starts (with an HTTP error status)."""
        async def _single_error():
            yield sse_error(code, message)

        resp = StreamingHttpResponse(_single_error(), content_type="text/event-stream", status=http_status)
        resp["Cache-Control"] = "no-cache"
        return resp

    @staticmethod
    async def _event_stream(chat_id: int, message: str, user_id: int, token: str):
        """
        Async generator that drives the SSE stream.

        Protocol
        --------
        1. ``start``    — emitted immediately after request validation.
        2. LLM call     — awaited; yields nothing while waiting.
        3. ``delta``    — one event per word of the assistant reply (streaming effect).
        4. ``complete`` — emitted once; includes the persisted message_id.

        On any error an ``error`` event is emitted and the stream closes.
        """
        try:
            # Signal to the client that we received the message and are processing.
            yield sse_start(chat_id)

            # Persist user message, call LLM, persist assistant reply.
            reply_msg = await _message_service.send_message_async(chat_id, message, user_id, token)

            # Stream the reply word-by-word to produce a "typing" effect.
            # The LLM service currently returns a full string, so we simulate
            # token-level streaming here.  When the LLM service gains native
            # streaming support, replace this loop with a real chunk iterator.
            words = reply_msg.message.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == len(words) - 1 else word + " "
                yield sse_delta(chunk)

            yield sse_complete(reply_msg.id, chat_id)

        except AppError as exc:
            logger.warning("Chat %d SSE application error: [%s] %s", chat_id, exc.code, exc.message)
            yield sse_error(exc.code, exc.message)
        except Exception:
            logger.exception("Chat %d SSE unexpected error", chat_id)
            yield sse_error("INTERNAL_ERROR", "An unexpected error occurred.")
