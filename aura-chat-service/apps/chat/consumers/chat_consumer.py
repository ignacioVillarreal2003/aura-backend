import asyncio
import json
import logging
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.chat import presence
from apps.chat.repositories.chat_repository import chat_repository
from apps.chat.ai_reply_lock import is_locked, refresh, release, try_acquire
from apps.artifact_message.exceptions import LLMServiceException
from apps.artifact_message.services.message_service import (
    ChatAIMode,
    broadcast_chat_ai_lock_change,
    message_service,
)
from apps.chat.ws_rate_limit import (
    acquire_ws_connection,
    check_message_rate_limit,
    check_typing_rate_limit,
    refresh_ws_connection,
    release_ws_connection,
)
from apps.membership.repositories.membership_repository import membership_repository
from apps.membership.models.chat_membership import ChatMembership
from apps.peer_message.services.peer_message_service import peer_message_service
from core.authentication.authenticated_user import AuthenticatedUser
from core.exceptions import ServiceUnavailableException

logger = logging.getLogger(__name__)

_MAX_MESSAGE_LENGTH = 10_000

_LOCK_REFRESH_INTERVAL_SECONDS = 30.0

# Refresh the Redis connection/presence lease well within their TTL so that a
# passive viewer (only receiving, never sending) does not have its slot reclaimed
# while still connected.
_LEASE_REFRESH_INTERVAL_SECONDS = 1800.0

# Strong references to in-flight AI-reply tasks. asyncio only keeps weak refs to
# tasks, so once the initiating consumer disconnects and drops its own handle the
# task could be garbage-collected mid-stream. Keeping it here lets the reply
# finish (and broadcast) for the remaining members of the chat.
_BACKGROUND_AI_TASKS: set[asyncio.Task] = set()


class ChatConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat_id: int | None = None
        self.group_name: str | None = None
        self.user: AuthenticatedUser | None = None
        self._ai_reply_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(self):
        try:
            self.chat_id = int(self.scope["url_route"]["kwargs"]["chat_id"])
        except (KeyError, ValueError, TypeError):
            await self.close(code=4003)
            return
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

        allowed = await database_sync_to_async(acquire_ws_connection)(
            self.user.id, self.channel_name
        )
        if not allowed:
            logger.warning(
                "WebSocket connection rejected: too many concurrent connections.",
                extra={"user_id": self.user.id},
            )
            await self.close(code=4029)
            return

        # Until accept() succeeds, disconnect() will not run, so any failure here
        # must release the just-reserved connection slot to avoid leaking it for
        # the whole lease TTL.
        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
        except Exception:
            await database_sync_to_async(release_ws_connection)(
                self.user.id, self.channel_name
            )
            logger.exception(
                "WebSocket accept failed; released connection slot.",
                extra={"chat_id": self.chat_id, "user_id": self.user.id},
            )
            raise

        is_first_presence = await database_sync_to_async(presence.join)(
            self.chat_id, self.user.id, self.channel_name
        )
        if is_first_presence:
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "presence_joined", "member_id": self.user.id},
            )

        self._heartbeat_task = asyncio.create_task(self._run_heartbeat())

        locked = await database_sync_to_async(is_locked)(self.chat_id)
        await self.send_json({"type": "chat_ai_lock", "locked": locked})

        logger.info(
            "WebSocket connected.",
            extra={"chat_id": self.chat_id, "user_id": self.user.id},
        )

    async def _run_heartbeat(self) -> None:
        try:
            while True:
                await asyncio.sleep(_LEASE_REFRESH_INTERVAL_SECONDS)
                if self.user is None:
                    return
                await database_sync_to_async(refresh_ws_connection)(
                    self.user.id, self.channel_name
                )
                if self.chat_id is not None:
                    await database_sync_to_async(presence.refresh)(
                        self.chat_id, self.user.id, self.channel_name
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "WebSocket heartbeat loop failed.",
                extra={"chat_id": self.chat_id, "user_id": getattr(self.user, "id", None)},
                exc_info=True,
            )

    async def disconnect(self, close_code):
        # Stop the heartbeat for this connection. The in-flight AI reply task is
        # intentionally NOT cancelled here: it keeps streaming to the rest of the
        # chat group and is held alive by _BACKGROUND_AI_TASKS.
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        self._ai_reply_task = None

        # Presence is reference-counted: only announce the user left when this was
        # their last open connection in the chat (avoids ghosting a user who just
        # closed one of several tabs).
        if self.group_name and self.user is not None and self.chat_id is not None:
            try:
                is_last_presence = await database_sync_to_async(presence.leave)(
                    self.chat_id, self.user.id, self.channel_name
                )
                if is_last_presence:
                    await self.channel_layer.group_send(
                        self.group_name,
                        {"type": "presence_left", "member_id": self.user.id},
                    )
            except Exception:
                logger.warning(
                    "Failed to update presence on disconnect.",
                    extra={"chat_id": self.chat_id, "user_id": self.user.id},
                )

        try:
            if self.group_name:
                await self.channel_layer.group_discard(
                    self.group_name, self.channel_name
                )
        finally:
            if self.user is not None:
                await database_sync_to_async(release_ws_connection)(
                    self.user.id, self.channel_name
                )
        logger.info(
            "WebSocket disconnected.",
            extra={
                "chat_id": self.chat_id,
                "user_id": getattr(self.user, "id", None),
                "close_code": close_code,
            },
        )

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if bytes_data is not None:
            await self.send_json({"type": "error", "detail": "Binary frames are not supported."})
            return
        if not text_data:
            return
        try:
            content = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self.send_json({"type": "error", "detail": "Invalid JSON payload."})
            return
        if not isinstance(content, dict):
            await self.send_json({"type": "error", "detail": "Payload must be a JSON object."})
            return
        await self.receive_json(content)

    async def receive_json(self, content, **kwargs):
        try:
            if self.user is not None:
                await database_sync_to_async(refresh_ws_connection)(
                    self.user.id, self.channel_name
                )
            msg_type = content.get("type")

            if msg_type == "chat.message":
                await self._handle_chat_message(content)
            elif msg_type == "chat.typing":
                await self._handle_typing(content)
            elif msg_type == "peer.message":
                await self._handle_peer_message(content)
            elif msg_type == "peer.message.edit":
                await self._handle_peer_message_edit(content)
            elif msg_type == "peer.message.delete":
                await self._handle_peer_message_delete(content)
            elif msg_type == "peer.typing":
                await self._handle_peer_typing(content)
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
        pre = await self._validate_send_preconditions(content)
        if pre is None:
            return
        text, mode, retrieve_context, process_documents = pre

        if not await self._enforce_rate_limit():
            return

        await self._cancel_previous_ai_reply()

        lock_token = await self._acquire_ai_lock()
        if lock_token is None:
            return

        if not await self._persist_user_message(text, lock_token):
            return

        self._spawn_ai_reply_task(mode, retrieve_context, process_documents, lock_token)

    async def _validate_send_preconditions(
            self, content: dict
    ) -> tuple[str, str, bool | None, bool | None] | None:
        """Run all send guards. Returns (text, mode) or sends an error and returns None.

        Validates membership/role BEFORE acquiring the AI lock so a reader (or a
        member removed mid-session) gets a precise error and we don't broadcast a
        spurious lock true->false flicker to the whole chat.
        """
        chat_obj = await database_sync_to_async(chat_repository.get_by_id)(self.chat_id)
        if chat_obj is None:
            await self.send_json({
                "type": "error",
                "error_code": "chat_not_found",
                "detail": "This chat no longer exists.",
            })
            return None
        if chat_obj.is_locked:
            await self.send_json({
                "type": "error",
                "error_code": "chat_locked",
                "detail": "This chat is locked and does not accept new messages.",
            })
            return None

        role = await database_sync_to_async(membership_repository.get_role)(
            self.chat_id, self.user.id
        )
        if role is None:
            await self.send_json({
                "type": "error",
                "error_code": "not_a_member",
                "detail": "You are no longer a member of this chat.",
            })
            return None
        if role == ChatMembership.Role.READER:
            await self.send_json({
                "type": "error",
                "error_code": "reader_cannot_send",
                "detail": "Readers cannot send messages in this chat.",
            })
            return None

        text = content.get("message", "").strip()
        if not text:
            await self.send_json({
                "type": "error",
                "detail": "Message cannot be empty",
            })
            return None
        if len(text) > _MAX_MESSAGE_LENGTH:
            await self.send_json({
                "type": "error",
                "error_code": "message_too_long",
                "detail": f"Message exceeds {_MAX_MESSAGE_LENGTH} characters.",
            })
            return None

        mode = ChatAIMode.normalize(content.get("mode"))
        retrieve_context = self._optional_bool(content.get("retrieve_context"))
        process_documents = self._optional_bool(content.get("process_documents"))
        return text, mode, retrieve_context, process_documents

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        """Coerce a raw WS payload value to a tri-state flag (True/False/None).

        Only genuine booleans are honoured; anything else (missing, null, string)
        falls back to None so the LLM service applies its own default.
        """
        return value if isinstance(value, bool) else None

    async def _enforce_rate_limit(self) -> bool:
        allowed = await database_sync_to_async(check_message_rate_limit)(
            self.user.id, self.chat_id
        )
        if not allowed:
            await self.send_json({
                "type": "error",
                "error_code": "rate_limit_exceeded",
                "detail": "Too many messages. Please wait before sending more.",
            })
            return False
        return True

    async def _cancel_previous_ai_reply(self) -> None:
        prev = self._ai_reply_task
        if prev is not None and not prev.done():
            prev.cancel()
            try:
                await prev
            except asyncio.CancelledError:
                pass

    async def _acquire_ai_lock(self) -> str | None:
        """Acquire the per-chat AI lock and broadcast the lock-on. Sends an error
        and returns None when the lock can't be taken."""
        try:
            lock_token = await database_sync_to_async(try_acquire)(self.chat_id)
        except ServiceUnavailableException as e:
            await self.send_json({
                "type": "error",
                "error_code": e.error_code,
                "detail": e.detail,
            })
            return None

        if not lock_token:
            await self.send_json({
                "type": "error",
                "error_code": "chat_ai_reply_in_progress",
                "detail": "Wait until the assistant finishes the current reply.",
            })
            return None

        await database_sync_to_async(broadcast_chat_ai_lock_change)(
            self.chat_id, True
        )
        return lock_token

    async def _persist_user_message(self, text: str, lock_token: str) -> bool:
        """Persist the user message. On failure releases the lock, broadcasts
        lock-off, sends an error and returns False."""
        try:
            await database_sync_to_async(message_service.send_message)(
                self.user, self.chat_id, text
            )
        except Exception:
            logger.exception(
                "Failed to save user message.",
                extra={"chat_id": self.chat_id, "user_id": self.user.id},
            )
            await database_sync_to_async(release)(self.chat_id, lock_token)
            await database_sync_to_async(broadcast_chat_ai_lock_change)(
                self.chat_id, False
            )
            await self.send_json({
                "type": "error",
                "detail": "Failed to save message. Please try again.",
            })
            return False
        return True

    def _spawn_ai_reply_task(
            self,
            mode: str,
            retrieve_context: bool | None,
            process_documents: bool | None,
            lock_token: str,
    ) -> None:
        task = asyncio.create_task(
            self._run_ai_reply(mode, retrieve_context, process_documents, lock_token)
        )
        # Hold a process-level strong reference so the reply survives even if this
        # consumer disconnects before the stream finishes.
        _BACKGROUND_AI_TASKS.add(task)

        def _on_ai_reply_done(t: asyncio.Task) -> None:
            _BACKGROUND_AI_TASKS.discard(t)
            if self._ai_reply_task is t:
                self._ai_reply_task = None
            if t.cancelled():
                return
            try:
                exc = t.exception()
            except Exception:
                logger.exception(
                    "Unexpected error reading AI-reply task result.",
                    extra={"chat_id": self.chat_id},
                )
                return
            if exc is not None:
                logger.error(
                    "AI-reply task failed.",
                    exc_info=exc,
                    extra={"chat_id": self.chat_id, "user_id": self.user.id, "mode": mode},
                )

        task.add_done_callback(_on_ai_reply_done)
        self._ai_reply_task = task

    async def _run_ai_reply(
            self,
            mode: str,
            retrieve_context: bool | None,
            process_documents: bool | None,
            lock_token: str,
    ):
        if self.group_name is None or self.chat_id is None:
            return
        try:
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "ai_meta", "chat_id": self.chat_id},
            )

            last_lock_refresh = 0.0
            try:
                async for payload in message_service.iter_ai_reply_stream_group_payloads(
                        mode, self.user, self.chat_id,
                        retrieve_context=retrieve_context,
                        process_documents=process_documents,
                ):
                    now = asyncio.get_running_loop().time()
                    if now - last_lock_refresh >= _LOCK_REFRESH_INTERVAL_SECONDS:
                        await database_sync_to_async(refresh)(self.chat_id, lock_token)
                        last_lock_refresh = now
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
                    "Error running AI-reply stream.",
                    extra={"chat_id": self.chat_id, "mode": mode},
                )
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "ai_error",
                        "detail": "AI service is temporarily unavailable",
                    },
                )
        finally:
            await database_sync_to_async(release)(self.chat_id, lock_token)
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

    # ── Peer chat (human-to-human, no AI) ─────────────────────────────────────
    async def _run_peer_service(self, fn, *args) -> bool:
        """Run a peer_message_service call off the event loop. On a known service
        error, relays its detail/error_code to the caller; otherwise logs and
        sends a generic error. The service broadcasts success to the group."""
        try:
            await database_sync_to_async(fn)(*args)
            return True
        except Exception as e:  # noqa: BLE001 - surfaced to the client below
            detail = getattr(e, "detail", None)
            error_code = getattr(e, "error_code", None)
            if detail is None:
                logger.exception(
                    "Unhandled error in peer chat operation.",
                    extra={"chat_id": self.chat_id, "user_id": getattr(self.user, "id", None)},
                )
                detail = "Failed to process message."
            out = {"type": "error", "detail": str(detail)}
            if error_code:
                out["error_code"] = error_code
            await self.send_json(out)
            return False

    async def _handle_peer_message(self, content: dict):
        text = content.get("message", "")
        text = text.strip() if isinstance(text, str) else ""
        if not text:
            await self.send_json({"type": "error", "detail": "Message cannot be empty"})
            return
        if len(text) > _MAX_MESSAGE_LENGTH:
            await self.send_json({
                "type": "error",
                "error_code": "message_too_long",
                "detail": f"Message exceeds {_MAX_MESSAGE_LENGTH} characters.",
            })
            return
        if not await self._enforce_rate_limit():
            return
        await self._run_peer_service(
            peer_message_service.create, self.user, self.chat_id, text
        )

    async def _handle_peer_message_edit(self, content: dict):
        message_id = content.get("id")
        if not isinstance(message_id, int):
            await self.send_json({"type": "error", "detail": "'id' must be an integer."})
            return
        text = content.get("message", "")
        text = text.strip() if isinstance(text, str) else ""
        if not text:
            await self.send_json({"type": "error", "detail": "Message cannot be empty"})
            return
        if len(text) > _MAX_MESSAGE_LENGTH:
            await self.send_json({
                "type": "error",
                "error_code": "message_too_long",
                "detail": f"Message exceeds {_MAX_MESSAGE_LENGTH} characters.",
            })
            return
        await self._run_peer_service(
            peer_message_service.update, self.user, self.chat_id, message_id, text
        )

    async def _handle_peer_message_delete(self, content: dict):
        message_id = content.get("id")
        if not isinstance(message_id, int):
            await self.send_json({"type": "error", "detail": "'id' must be an integer."})
            return
        await self._run_peer_service(
            peer_message_service.delete, self.user, self.chat_id, message_id
        )

    async def _handle_peer_typing(self, content: dict):
        is_typing = content.get("is_typing")
        if not isinstance(is_typing, bool):
            await self.send_json({"type": "error", "detail": "'is_typing' must be a boolean."})
            return
        allowed = await database_sync_to_async(check_typing_rate_limit)(self.user.id)
        if not allowed:
            return
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "peer_typing", "user_id": self.user.id, "is_typing": is_typing},
        )

    async def peer_message_created(self, event):
        await self.send_json({
            "type": "peer_message_created",
            "id": event["id"],
            "chat_id": event["chat_id"],
            "message": event["message"],
            "created_by": event["created_by"],
            "created_at": event["created_at"],
            "updated_at": event.get("updated_at"),
            "is_edited": event.get("is_edited", False),
        })

    async def peer_message_updated(self, event):
        await self.send_json({
            "type": "peer_message_updated",
            "id": event["id"],
            "chat_id": event["chat_id"],
            "message": event["message"],
            "created_by": event["created_by"],
            "created_at": event["created_at"],
            "updated_at": event.get("updated_at"),
            "is_edited": event.get("is_edited", True),
        })

    async def peer_message_deleted(self, event):
        await self.send_json({
            "type": "peer_message_deleted",
            "id": event["id"],
            "deleted_by": event.get("deleted_by"),
        })

    async def peer_typing(self, event):
        if self.user is None:
            return
        if event["user_id"] != self.user.id:
            await self.send_json({
                "type": "peer_typing",
                "user_id": event["user_id"],
                "is_typing": event["is_typing"],
            })

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
        if self.user is None:
            return
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

    async def artifact_created(self, event):
        await self.send_json({
            "type": "artifact_created",
            "artifact_id": event["artifact_id"],
            "artifact_type": event["artifact_type"],
            "title": event.get("title", ""),
            "created_by": event["created_by"],
            "created_at": event["created_at"],
        })

    async def artifact_deleted(self, event):
        await self.send_json({
            "type": "artifact_deleted",
            "artifact_id": event["artifact_id"],
            "deleted_by": event.get("deleted_by"),
        })

    async def member_left(self, event):
        await self.send_json({
            "type": "member_left",
            "member_id": event["member_id"],
        })

    async def presence_joined(self, event):
        await self.send_json({
            "type": "presence_joined",
            "member_id": event["member_id"],
        })

    async def presence_left(self, event):
        await self.send_json({
            "type": "presence_left",
            "member_id": event["member_id"],
        })

    async def chat_content_cleared(self, event):
        await self.send_json({
            "type": "chat_content_cleared",
            "by": event.get("by"),
        })

    async def chat_deleted(self, event):
        # The chat is gone; notify this client and close its socket so it stops
        # listening on a dead group.
        await self.send_json({
            "type": "chat_deleted",
            "by": event.get("by"),
        })
        await self.close(code=4004)

    async def membership_revoked(self, event):
        # Only the member who lost access reacts; everyone else keeps the socket.
        if self.user is not None and event.get("member_id") == self.user.id:
            await self.send_json({
                "type": "membership_revoked",
                "member_id": event["member_id"],
            })
            await self.close(code=4003)
