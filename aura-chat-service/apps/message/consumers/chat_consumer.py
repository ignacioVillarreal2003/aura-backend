import asyncio
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.message.exceptions import LLMServiceException
from apps.message.serializers.response import MessageResponse
from apps.message.services.message_service import message_service
from apps.membership.repositories.membership_repository import membership_repository
from core.authentication.authenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)


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

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

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
        logger.info(
            "WebSocket disconnected.",
            extra={
                "chat_id": self.chat_id,
                "user_id": getattr(self.user, "id", None),
                "close_code": close_code,
            },
        )

    async def receive_json(self, content, **kwargs):
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

    async def _handle_chat_message(self, content: dict):
        text = content.get("message", "").strip()
        if not text:
            await self.send_json({
                "type": "error",
                "detail": "Message cannot be empty",
            })
            return

        user_msg = await database_sync_to_async(message_service.send_message)(
            self.user, self.chat_id, text
        )

        user_payload = MessageResponse(user_msg).data

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "user_message",
                **user_payload,
            },
        )

        prev = self._document_question_task
        if prev is not None and not prev.done():
            prev.cancel()

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

    async def _handle_typing(self, content: dict):
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "typing",
                "user_id": self.user.id,
                "is_typing": content.get("is_typing", True),
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

    async def typing(self, event):
        if event["user_id"] != self.user.id:
            await self.send_json({
                "type": "typing",
                "user_id": event["user_id"],
                "is_typing": event["is_typing"],
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
