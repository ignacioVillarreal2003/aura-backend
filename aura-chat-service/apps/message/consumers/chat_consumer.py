import asyncio
import logging
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.chat.repositories.chat_repository import chat_repository
from apps.message.chat_ai_reply_lock import is_locked, release, try_acquire
from apps.message.exceptions import LLMServiceException
from apps.message.services.message_service import (
    broadcast_chat_ai_lock_change,
    message_service,
)
from apps.message.ws_rate_limit import (
    acquire_ws_connection,
    check_message_rate_limit,
    check_typing_rate_limit,
    release_ws_connection,
)
from apps.membership.repositories.membership_repository import membership_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.exceptions import ServiceUnavailableException

logger = logging.getLogger(__name__)

_MAX_MESSAGE_LENGTH = 10_000


class ChatConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat_id: int | None = None
        self.group_name: str | None = None
        self.user: AuthenticatedUser | None = None
        self._document_question_task: asyncio.Task | None = None

    async def connect(self):
        self.chat_id = int(self.scope["url_route"]["kwargs"]["chat_id"])
        self.group_name = f"chat_{self.chat_id}"
        self.user = self.scope.get("user")

        if self.user is None:
            await self.close(code=4001)
            return

        is_member = await database_sync_to_async(
            membership_repository.is_active_member
        )(self.chat_id, self.user.id)

        if not is_member:
            await self.close(code=4003)
            return

        allowed = await database_sync_to_async(acquire_ws_connection)(self.user.id)
        if not allowed:
            logger.warning(
                "WebSocket connection rejected: too many concurrent connections.",
                extra={"user_id": self.user.id},
            )
            await self.close(code=4029)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        locked = await database_sync_to_async(is_locked)(self.chat_id)
        await self.send_json({"type": "chat_ai_lock", "locked": locked})

        logger.info(
            "WebSocket connected.",
            extra={"chat_id": self.chat_id, "user_id": self.user.id},
        )

    async def disconnect(self, close_code):
        t = self._document_question_task
        if t is not None and not t.done():
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception(
                    "Error awaiting cancelled document-question task.",
                    extra={"chat_id": self.chat_id},
                )
        self._document_question_task = None

        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )
        if self.user is not None:
            await database_sync_to_async(release_ws_connection)(self.user.id)
        logger.info(
            "WebSocket disconnected.",
            extra={
                "chat_id": self.chat_id,
                "user_id": getattr(self.user, "id", None),
                "close_code": close_code,
            },
        )

    async def receive_json(self, content, **kwargs):
        try:
            msg_type = content.get("type")

            if msg_type == "chat.message":
                await self._handle_chat_message(content)
            elif msg_type == "chat.typing":
                await self._handle_typing(content)
            else:
                await self.send_json({
                    "type": "error",
                    "detail": f"Unknown message type: {msg_type}",
                })
        except Exception:
            logger.exception(
                "Unhandled error in receive_json.",
                extra={"chat_id": self.chat_id, "user_id": getattr(self.user, "id", None)},
            )
            try:
                await self.send_json({"type": "error", "detail": "Internal server error."})
            except Exception:
                pass

    async def _handle_chat_message(self, content: dict):
        chat_obj = await database_sync_to_async(chat_repository.get_by_id)(self.chat_id)
        if chat_obj is not None and chat_obj.is_locked:
            await self.send_json({
                "type": "error",
                "error_code": "chat_locked",
                "detail": "This chat is locked and does not accept new messages.",
            })
            return

        text = content.get("message", "").strip()
        if not text:
            await self.send_json({
                "type": "error",
                "detail": "Message cannot be empty",
            })
            return

        if len(text) > _MAX_MESSAGE_LENGTH:
            await self.send_json({
                "type": "error",
                "error_code": "message_too_long",
                "detail": f"Message exceeds {_MAX_MESSAGE_LENGTH} characters.",
            })
            return

        allowed = await database_sync_to_async(check_message_rate_limit)(
            self.user.id, self.chat_id
        )
        if not allowed:
            await self.send_json({
                "type": "error",
                "error_code": "rate_limit_exceeded",
                "detail": "Too many messages. Please wait before sending more.",
            })
            return

        prev = self._document_question_task
        if prev is not None and not prev.done():
            prev.cancel()
            try:
                await prev
            except asyncio.CancelledError:
                pass

        try:
            acquired = await database_sync_to_async(try_acquire)(self.chat_id)
        except ServiceUnavailableException as e:
            await self.send_json({
                "type": "error",
                "error_code": e.error_code,
                "detail": e.detail,
            })
            return

        if not acquired:
            await self.send_json({
                "type": "error",
                "error_code": "chat_ai_reply_in_progress",
                "detail": "Wait until the assistant finishes the current reply.",
            })
            return

        await database_sync_to_async(broadcast_chat_ai_lock_change)(
            self.chat_id, True
        )

        try:
            await database_sync_to_async(message_service.send_message)(
                self.user, self.chat_id, text
            )
        except Exception:
            logger.exception(
                "Failed to save user message.",
                extra={"chat_id": self.chat_id, "user_id": self.user.id},
            )
            await database_sync_to_async(release)(self.chat_id)
            await database_sync_to_async(broadcast_chat_ai_lock_change)(
                self.chat_id, False
            )
            await self.send_json({
                "type": "error",
                "detail": "Failed to save message. Please try again.",
            })
            return

        task = asyncio.create_task(self._run_document_question())

        def _on_document_question_done(t: asyncio.Task) -> None:
            if self._document_question_task is t:
                self._document_question_task = None
            if t.cancelled():
                return
            try:
                exc = t.exception()
            except Exception:
                logger.exception(
                    "Unexpected error reading document-question task result.",
                    extra={"chat_id": self.chat_id},
                )
                return
            if exc is not None:
                logger.error(
                    "Document-question task failed.",
                    exc_info=exc,
                    extra={"chat_id": self.chat_id, "user_id": self.user.id},
                )

        task.add_done_callback(_on_document_question_done)
        self._document_question_task = task

    async def _run_document_question(self):
        try:
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "ai_meta", "chat_id": self.chat_id},
            )

            try:
                async for payload in message_service.iter_document_question_stream_group_payloads(
                    self.user, self.chat_id
                ):
                    await self.channel_layer.group_send(self.group_name, payload)
            except LLMServiceException:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "ai_error",
                        "detail": "AI service is temporarily unavailable",
                    },
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Error running document-question stream.",
                    extra={"chat_id": self.chat_id},
                )
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "ai_error",
                        "detail": "AI service is temporarily unavailable",
                    },
                )
        finally:
            await database_sync_to_async(release)(self.chat_id)
            try:
                await database_sync_to_async(broadcast_chat_ai_lock_change)(
                    self.chat_id, False
                )
            except Exception:
                logger.warning(
                    "Failed to broadcast ai_lock_change release for chat %d",
                    self.chat_id,
                    exc_info=True,
                )

    async def _handle_typing(self, content: dict):
        is_typing = content.get("is_typing")
        if not isinstance(is_typing, bool):
            await self.send_json({
                "type": "error",
                "detail": "'is_typing' must be a boolean.",
            })
            return

        allowed = await database_sync_to_async(check_typing_rate_limit)(self.user.id)
        if not allowed:
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "typing",
                "user_id": self.user.id,
                "is_typing": is_typing,
            },
        )

    async def user_message(self, event):
        await self.send_json({
            "type": "user_message",
            "id": event["id"],
            "message": event["message"],
            "sender_type": event["sender_type"],
            "created_by": event["created_by"],
            "created_at": event["created_at"],
        })

    async def ai_meta(self, event):
        await self.send_json({
            "type": "ai_meta",
            "chat_id": event["chat_id"],
        })

    async def ai_context(self, event):
        await self.send_json({
            "type": "ai_context",
            "question": event.get("question", ""),
            "fragments": event.get("fragments", []),
        })

    async def ai_progress(self, event):
        await self.send_json({
            "type": "ai_progress",
            "step": event.get("step", ""),
            "message": event.get("message", ""),
        })

    async def ai_delta(self, event):
        await self.send_json({
            "type": "ai_delta",
            "delta": event["delta"],
        })

    async def ai_complete(self, event):
        payload = {
            "type": "ai_complete",
            "message": event.get("message", ""),
            "answer": event.get("answer", ""),
            "question": event.get("question", ""),
            "fragments": event.get("fragments", []),
        }
        if "id" in event:
            payload["id"] = event["id"]
            payload["sender_type"] = event["sender_type"]
            payload["created_by"] = event["created_by"]
            payload["created_at"] = event["created_at"]
        await self.send_json(payload)

    async def ai_error(self, event):
        out = {
            "type": "ai_error",
            "detail": event["detail"],
        }
        if event.get("code") is not None:
            out["code"] = event["code"]
        await self.send_json(out)

    async def chat_ai_lock_changed(self, event):
        await self.send_json({
            "type": "chat_ai_lock",
            "locked": event["locked"],
        })

    async def typing(self, event):
        if event["user_id"] != self.user.id:
            await self.send_json({
                "type": "typing",
                "user_id": event["user_id"],
                "is_typing": event["is_typing"],
            })

    async def chat_locked_changed(self, event):
        await self.send_json({
            "type": "chat_locked_changed",
            "is_locked": event["is_locked"],
            "by": event.get("by"),
        })

    async def member_joined(self, event):
        await self.send_json({
            "type": "member_joined",
            "member_id": event["member_id"],
        })

    async def member_left(self, event):
        await self.send_json({
            "type": "member_left",
            "member_id": event["member_id"],
        })
