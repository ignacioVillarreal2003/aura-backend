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

        await self._run_document_question()

    async def _run_document_question(self):
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "ai_meta", "chat_id": self.chat_id},
        )

        try:
            result = await message_service.run_document_question(
                self.user, self.chat_id
            )
        except LLMServiceException:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "ai_error",
                    "detail": "AI service is temporarily unavailable",
                },
            )
            return
        except Exception:
            logger.exception(
                "Error running document-question.",
                extra={"chat_id": self.chat_id},
            )
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "ai_error",
                    "detail": "AI service is temporarily unavailable",
                },
            )
            return

        event = {
            "type": "ai_complete",
            "message": result.answer,
            "answer": result.answer,
            "question": result.question,
            "fragments": result.fragments,
        }
        if result.assistant_message:
            am = result.assistant_message
            event["id"] = am.id
            event["sender_type"] = am.sender_type
            event["created_by"] = am.created_by
            event["created_at"] = am.created_at.isoformat()

        await self.channel_layer.group_send(self.group_name, event)

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
        await self.send_json({
            "type": "ai_error",
            "detail": event["detail"],
        })

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
