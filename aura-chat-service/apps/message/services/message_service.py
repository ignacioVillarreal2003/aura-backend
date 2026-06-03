import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import (
    ChatLockedException,
    LLMServiceException,
    MessageAccessDeniedException,
    MessageDeleteForbiddenException,
    MessageNotFoundException,
    NoMessageToRegenerateException,
    NotChatOwnerException,
    ReaderCannotSendMessageException,
    TranscriptionBusyException,
    TranscriptionException,
)
from apps.artifact.models.artifact_message import ArtifactMessage
from apps.artifact.models.artifact_message import ArtifactMessage as ChatMessage  # backward compat
from apps.message.repositories.feedback_repository import feedback_repository
from apps.message.repositories.message_repository import message_repository
from apps.message.serializers.response import MessageResponse
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import (
    CLEAR_CHAT_HISTORY,
    DELETE_MESSAGE,
    LIST_MESSAGES,
    MANAGE_CHATS,
    REGENERATE_AI_RESPONSE,
    SEND_MESSAGE,
)
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import (
    AgentRunResult,
    DocumentQuestionResult,
    GeneralChatResult,
    llm_client,
)
from core.clients.transcription_client import TranscriptionBusyError, transcription_client

logger = logging.getLogger(__name__)


class ChatAIMode:
    """Selectable AI reply flows backed by the LLM service.

    Each mode maps to a distinct LLM-service controller:
      * ``document_question`` -> RAG question answering over the user's documents.
      * ``general_chat``      -> general-purpose assistant (no RAG, history only).
      * ``rag_agent``         -> full RAG agent pipeline (analyse/retrieve/reason).
      * ``agent``             -> tool-using agent (document question/summary tools).
    """

    DOCUMENT_QUESTION = "document_question"
    GENERAL_CHAT = "general_chat"
    RAG_AGENT = "rag_agent"
    AGENT = "agent"

    DEFAULT = DOCUMENT_QUESTION
    ALL = frozenset({DOCUMENT_QUESTION, GENERAL_CHAT, RAG_AGENT, AGENT})

    @classmethod
    def normalize(cls, value: Any) -> str:
        """Return a valid mode, defaulting to ``document_question``."""
        if isinstance(value, str) and value in cls.ALL:
            return value
        return cls.DEFAULT


def _broadcast_user_message_to_chat_group(chat_id: int, msg: ArtifactMessage) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    payload = MessageResponse(msg).data
    try:
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat_id}",
            {"type": "user_message", **payload},
        )
    except Exception:
        logger.warning(
            "Failed to broadcast user_message for chat %d", chat_id, exc_info=True
        )


def broadcast_chat_ai_lock_change(chat_id: int, locked: bool) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat_id}",
            {"type": "chat_ai_lock_changed", "locked": locked},
        )
    except Exception:
        logger.warning(
            "Failed to broadcast ai_lock_change for chat %d", chat_id, exc_info=True
        )


@dataclass
class DocumentQuestionRunResult:
    question: str
    answer: str
    fragments: list[dict[str, Any]]
    assistant_message: ArtifactMessage | None = None


class MessageService:
    def transcribe_audio(self, audio_file) -> str:
        try:
            return transcription_client.transcribe(audio_file)
        except TranscriptionBusyError as e:
            raise TranscriptionBusyException() from e
        except Exception as e:
            raise TranscriptionException() from e

    def send_message(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            text: str,
    ) -> ArtifactMessage:
        AccessControl.require_permissions(user, frozenset({SEND_MESSAGE}))
        self._require_send_access(chat_id, user.id)

        with transaction.atomic():
            msg = message_repository.create(
                chat_id=chat_id,
                message=text,
                sender_type=ArtifactMessage.SenderType.USER,
                created_by=user.id,
            )
            chat_repository.touch_last_message_at(chat_id, updated_by=user.id)

        logger.info(
            "User message saved.",
            extra={"chat_id": chat_id, "message_id": msg.id, "user_id": user.id},
        )
        _broadcast_user_message_to_chat_group(chat_id, msg)
        return msg

    def _save_ai_message(
            self,
            chat_id: int,
            user_id: int,
            answer: str,
            fragments: list | None = None,
    ) -> ArtifactMessage:
        with transaction.atomic():
            msg = message_repository.create(
                chat_id=chat_id,
                message=answer,
                sender_type=ArtifactMessage.SenderType.SYSTEM,
                created_by=user_id,
                fragments=fragments or None,
            )
            chat_repository.touch_last_message_at(chat_id, updated_by=user_id)
        return msg

    def get_messages(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({LIST_MESSAGES}))
        self._require_access(chat_id, user.id)
        return message_repository.get_messages_by_chat(chat_id, user_id=user.id)

    def get_messages_admin(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({MANAGE_CHATS}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        return message_repository.get_messages_by_chat(chat_id, user_id=user.id)

    def clear_history(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({CLEAR_CHAT_HISTORY}))
        self._require_access(chat_id, user.id)
        if not membership_repository.is_chat_owner(chat_id, user.id):
            raise NotChatOwnerException()
        message_repository.soft_delete_by_chat(chat_id, deleted_by=user.id)
        logger.info("Chat history cleared.", extra={"chat_id": chat_id, "user_id": user.id})

    def delete_last_ai_message(self, user: AuthenticatedUser, chat_id: int) -> str | None:
        """Delete the last AI message ahead of a regeneration.

        Returns a natural-language hint built from the requesting user's negative
        feedback on that message (if any), so the regenerated answer can correct
        what the user disliked. Returns ``None`` when there is no actionable
        feedback (no feedback, or a thumbs up).
        """
        AccessControl.require_permissions(user, frozenset({REGENERATE_AI_RESPONSE}))
        self._require_access(chat_id, user.id)
        last_ai = message_repository.get_last_ai_message(chat_id)
        if last_ai is None:
            raise NoMessageToRegenerateException()
        hint = self._regen_hint_from_feedback(last_ai.artifact_id, user.id)
        last_ai.delete(deleted_by=user.id)
        logger.info(
            "Last AI message deleted for regeneration.",
            extra={"chat_id": chat_id, "message_id": last_ai.id, "has_feedback_hint": hint is not None},
        )
        return hint

    @staticmethod
    def _regen_hint_from_feedback(artifact_id: int, user_id: int) -> str | None:
        from apps.message.models.message_feedback import ArtifactFeedback

        fb = feedback_repository.get(artifact_id=artifact_id, user_id=user_id)
        if fb is None or fb.value != ArtifactFeedback.Value.THUMBS_DOWN:
            return None

        reason_text = {
            ArtifactFeedback.Reason.INCORRECT: "la información era incorrecta",
            ArtifactFeedback.Reason.INCOMPLETE: "la respuesta estaba incompleta",
            ArtifactFeedback.Reason.OFF_TOPIC: "no respondía lo que se preguntó",
            ArtifactFeedback.Reason.TONE: "el tono o estilo no era adecuado",
            ArtifactFeedback.Reason.TOO_LONG: "era demasiado larga o verbosa",
            ArtifactFeedback.Reason.HALLUCINATION: "incluía datos inventados o no verificables",
        }.get(fb.reason)

        parts = [
            "El usuario marcó tu respuesta anterior como NO útil y pidió regenerarla.",
        ]
        if reason_text:
            parts.append(f"Motivo indicado: {reason_text}.")
        comment = (fb.comment or "").strip()
        if comment:
            parts.append(f'Comentario del usuario: "{comment}".')
        parts.append(
            "Generá una nueva respuesta que corrija específicamente ese problema, "
            "manteniendo lo que sí era correcto."
        )
        return " ".join(parts)

    @staticmethod
    async def _build_llm_messages(
            chat_id: int,
            extra_instruction: str | None = None,
    ) -> list[dict[str, str]]:
        limit = getattr(settings, "LLM_CONTEXT_MESSAGE_LIMIT", 10)
        recent = await sync_to_async(message_repository.get_recent_messages)(
            chat_id, limit=limit
        )
        messages: list[dict[str, str]] = []
        for m in reversed(recent):
            if m.sender_type == ArtifactMessage.SenderType.USER:
                messages.append({"role": "human", "content": m.message})
            elif m.sender_type in (ArtifactMessage.SenderType.SYSTEM, ArtifactMessage.SenderType.ASSISTANT):
                messages.append({"role": "assistant", "content": m.message})
        if extra_instruction:
            # Appended as a final human turn so every mode (general/rag/agent/document)
            # picks it up uniformly, since only `general_chat` carries a system prompt.
            messages.append({"role": "human", "content": extra_instruction})
        return messages

    async def run_document_question(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            regen_feedback: str | None = None,
    ) -> DocumentQuestionRunResult:
        await sync_to_async(self._require_access)(chat_id, user.id)

        messages = await self._build_llm_messages(chat_id, extra_instruction=regen_feedback)

        try:
            llm_out: DocumentQuestionResult = await llm_client.document_question(
                messages, user, chat_id=chat_id
            )
        except HttpClientException as e:
            logger.error(
                "LLM document-question failed: %s",
                str(e),
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "status_code": e.status_code,
                    "llm_url": getattr(settings, "LLM_DOCUMENT_QUESTION_URL", ""),
                },
                exc_info=True,
            )
            raise LLMServiceException() from e

        assistant_msg: ArtifactMessage | None = None
        if llm_out.answer.strip():
            assistant_msg = await sync_to_async(self._save_ai_message)(
                chat_id, user.id, llm_out.answer, llm_out.fragments or None
            )
            logger.info(
                "AI response saved.",
                extra={"chat_id": chat_id, "message_id": assistant_msg.id},
            )

        return DocumentQuestionRunResult(
            question=llm_out.question,
            answer=llm_out.answer,
            fragments=llm_out.fragments,
            assistant_message=assistant_msg,
        )

    # ------------------------------------------------------------------
    # Non-streaming AI replies (REST request/response)
    # ------------------------------------------------------------------
    async def run_ai_reply(
            self,
            mode: str,
            user: AuthenticatedUser,
            chat_id: int,
            regen_feedback: str | None = None,
    ) -> DocumentQuestionRunResult:
        """Run a single AI reply turn for the requested mode and persist it.

        ``regen_feedback`` is an optional instruction (built from the user's
        negative feedback) injected into the LLM context to steer a regeneration.
        """
        if mode == ChatAIMode.GENERAL_CHAT:
            return await self.run_general_chat(user, chat_id, regen_feedback=regen_feedback)
        if mode == ChatAIMode.RAG_AGENT:
            return await self.run_rag_agent(user, chat_id, regen_feedback=regen_feedback)
        if mode == ChatAIMode.AGENT:
            return await self.run_agent(user, chat_id, regen_feedback=regen_feedback)
        return await self.run_document_question(user, chat_id, regen_feedback=regen_feedback)

    async def run_general_chat(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            regen_feedback: str | None = None,
    ) -> DocumentQuestionRunResult:
        await sync_to_async(self._require_access)(chat_id, user.id)
        messages = await self._build_llm_messages(chat_id, extra_instruction=regen_feedback)
        system_prompt = await self._get_chat_system_prompt(chat_id)
        try:
            result: GeneralChatResult = await llm_client.general_chat(
                messages, user, system_prompt=system_prompt
            )
        except HttpClientException as e:
            logger.error(
                "LLM general-chat failed: %s",
                str(e),
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "status_code": e.status_code,
                    "llm_url": getattr(settings, "LLM_GENERAL_CHAT_URL", ""),
                },
                exc_info=True,
            )
            raise LLMServiceException() from e

        assistant_msg = await self._persist_ai_answer(chat_id, user.id, result.answer, None)
        return DocumentQuestionRunResult(
            question="",
            answer=result.answer,
            fragments=[],
            assistant_message=assistant_msg,
        )

    async def run_rag_agent(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            regen_feedback: str | None = None,
    ) -> DocumentQuestionRunResult:
        return await self._run_agent_flow(
            user=user,
            chat_id=chat_id,
            caller=llm_client.rag_agent,
            url_setting_name="LLM_RAG_AGENT_URL",
            label="rag-agent",
            regen_feedback=regen_feedback,
        )

    async def run_agent(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            regen_feedback: str | None = None,
    ) -> DocumentQuestionRunResult:
        return await self._run_agent_flow(
            user=user,
            chat_id=chat_id,
            caller=llm_client.agent,
            url_setting_name="LLM_AGENT_URL",
            label="agent",
            regen_feedback=regen_feedback,
        )

    async def _run_agent_flow(
            self,
            *,
            user: AuthenticatedUser,
            chat_id: int,
            caller: Callable[..., Any],
            url_setting_name: str,
            label: str,
            regen_feedback: str | None = None,
    ) -> DocumentQuestionRunResult:
        await sync_to_async(self._require_access)(chat_id, user.id)
        messages = await self._build_llm_messages(chat_id, extra_instruction=regen_feedback)
        try:
            result: AgentRunResult = await caller(messages, user)
        except HttpClientException as e:
            logger.error(
                "LLM %s failed: %s",
                label,
                str(e),
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "status_code": e.status_code,
                    "llm_url": getattr(settings, url_setting_name, ""),
                },
                exc_info=True,
            )
            raise LLMServiceException() from e

        assistant_msg = await self._persist_ai_answer(
            chat_id, user.id, result.answer, result.fragments or None
        )
        return DocumentQuestionRunResult(
            question="",
            answer=result.answer,
            fragments=result.fragments,
            assistant_message=assistant_msg,
        )

    async def _persist_ai_answer(
            self,
            chat_id: int,
            user_id: int,
            answer: str,
            fragments: list | None,
    ) -> ArtifactMessage | None:
        if not answer or not answer.strip():
            return None
        assistant_msg = await sync_to_async(self._save_ai_message)(
            chat_id, user_id, answer, fragments
        )
        logger.info(
            "AI response saved.",
            extra={"chat_id": chat_id, "message_id": assistant_msg.id},
        )
        return assistant_msg

    # ------------------------------------------------------------------
    # Streaming AI replies (WebSocket group payloads)
    # ------------------------------------------------------------------
    def iter_ai_reply_stream_group_payloads(
            self,
            mode: str,
            user: AuthenticatedUser,
            chat_id: int,
            regen_feedback: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Return the streaming group-payload iterator for the requested mode.

        Returns the async generator itself (it is not awaited) so the caller can
        iterate it directly, mirroring the existing document-question flow.

        ``regen_feedback`` is an optional instruction (built from the user's
        negative feedback) injected into the LLM context to steer a regeneration.
        """
        if mode == ChatAIMode.GENERAL_CHAT:
            return self.iter_general_chat_stream_group_payloads(user, chat_id, regen_feedback)
        if mode == ChatAIMode.RAG_AGENT:
            return self.iter_rag_agent_stream_group_payloads(user, chat_id, regen_feedback)
        if mode == ChatAIMode.AGENT:
            return self.iter_agent_stream_group_payloads(user, chat_id, regen_feedback)
        return self.iter_document_question_stream_group_payloads(user, chat_id, regen_feedback)

    async def iter_document_question_stream_group_payloads(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            regen_feedback: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        await sync_to_async(self._require_access)(chat_id, user.id)
        messages = await self._build_llm_messages(chat_id, extra_instruction=regen_feedback)
        async for payload in self._iter_ai_stream_group_payloads(
                chat_id=chat_id,
                user=user,
                sse_events=llm_client.document_question_stream_events(
                    messages, user, chat_id=chat_id
                ),
                complete_extractor=self._extract_document_question_complete,
                stream_url_setting_name="LLM_DOCUMENT_QUESTION_STREAM_URL",
        ):
            yield payload

    async def iter_general_chat_stream_group_payloads(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            regen_feedback: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        await sync_to_async(self._require_access)(chat_id, user.id)
        messages = await self._build_llm_messages(chat_id, extra_instruction=regen_feedback)
        system_prompt = await self._get_chat_system_prompt(chat_id)
        async for payload in self._iter_ai_stream_group_payloads(
                chat_id=chat_id,
                user=user,
                sse_events=llm_client.general_chat_stream_events(
                    messages, user, system_prompt=system_prompt
                ),
                complete_extractor=self._extract_general_chat_complete,
                stream_url_setting_name="LLM_GENERAL_CHAT_STREAM_URL",
        ):
            yield payload

    async def iter_rag_agent_stream_group_payloads(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            regen_feedback: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        await sync_to_async(self._require_access)(chat_id, user.id)
        messages = await self._build_llm_messages(chat_id, extra_instruction=regen_feedback)
        async for payload in self._iter_ai_stream_group_payloads(
                chat_id=chat_id,
                user=user,
                sse_events=llm_client.rag_agent_stream_events(messages, user),
                complete_extractor=self._extract_agent_complete,
                stream_url_setting_name="LLM_RAG_AGENT_STREAM_URL",
        ):
            yield payload

    async def iter_agent_stream_group_payloads(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            regen_feedback: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        await sync_to_async(self._require_access)(chat_id, user.id)
        messages = await self._build_llm_messages(chat_id, extra_instruction=regen_feedback)
        async for payload in self._iter_ai_stream_group_payloads(
                chat_id=chat_id,
                user=user,
                sse_events=llm_client.agent_stream_events(messages, user),
                complete_extractor=self._extract_agent_complete,
                stream_url_setting_name="LLM_AGENT_STREAM_URL",
        ):
            yield payload

    async def _iter_ai_stream_group_payloads(
            self,
            *,
            chat_id: int,
            user: AuthenticatedUser,
            sse_events: AsyncIterator[dict[str, Any]],
            complete_extractor: Callable[
                [dict[str, Any], str, str, list[Any]], tuple[str, str, list[Any]]
            ],
            stream_url_setting_name: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Consume an LLM SSE event stream and yield WebSocket group payloads.

        Handles the union of event types emitted by the LLM streaming
        controllers (``meta``, ``progress``, ``delta``, ``complete``, ``error``);
        modes that never emit a given event simply skip that branch. The
        assistant message is persisted on ``complete`` (or via the accumulated
        deltas as a fallback when the stream ends without a ``complete``).
        """
        accumulated_answer = ""
        received_complete = False
        had_error = False
        last_question = ""
        last_fragments: list[Any] = []

        async def _build_and_save_complete() -> dict[str, Any] | None:
            answer = accumulated_answer.strip()
            if not answer:
                return None
            assistant_msg: ChatMessage | None = None
            try:
                assistant_msg = await sync_to_async(self._save_ai_message)(
                    chat_id, user.id, answer, last_fragments or None
                )
                logger.info(
                    "AI response saved (stream fallback).",
                    extra={"chat_id": chat_id, "message_id": assistant_msg.id},
                )
            except Exception:
                logger.exception(
                    "Failed to save fallback AI message.",
                    extra={"chat_id": chat_id},
                )
            event: dict[str, Any] = {
                "type": "ai_complete",
                "message": answer,
                "answer": answer,
                "question": last_question,
                "fragments": last_fragments,
            }
            if assistant_msg:
                event["id"] = assistant_msg.id
                event["sender_type"] = assistant_msg.sender_type
                event["created_by"] = assistant_msg.created_by
                event["created_at"] = assistant_msg.created_at.isoformat()
            return event

        try:
            async for sse in sse_events:
                et = sse.get("type")
                if et == "meta":
                    last_question = str(sse.get("question", ""))
                    last_fragments = llm_client.normalize_fragments(sse.get("fragments"))
                    yield {
                        "type": "ai_context",
                        "question": last_question,
                        "fragments": last_fragments,
                    }
                elif et == "progress":
                    yield {
                        "type": "ai_progress",
                        "step": str(sse.get("step", "")),
                        "message": str(sse.get("message", "")),
                    }
                elif et == "delta":
                    delta = str(sse.get("text", ""))
                    accumulated_answer += delta
                    yield {
                        "type": "ai_delta",
                        "delta": delta,
                    }
                elif et == "complete":
                    received_complete = True
                    result = sse.get("result") or {}
                    if not isinstance(result, dict):
                        result = {}
                    q, answer, fragments = complete_extractor(
                        result, accumulated_answer, last_question, last_fragments
                    )

                    assistant_msg: ArtifactMessage | None = None
                    if answer:
                        assistant_msg = await sync_to_async(self._save_ai_message)(
                            chat_id, user.id, answer, fragments or None
                        )
                        logger.info(
                            "AI response saved (stream).",
                            extra={
                                "chat_id": chat_id,
                                "message_id": assistant_msg.id,
                            },
                        )

                    event: dict[str, Any] = {
                        "type": "ai_complete",
                        "message": answer,
                        "answer": answer,
                        "question": q,
                        "fragments": fragments,
                    }
                    if assistant_msg:
                        event["id"] = assistant_msg.id
                        event["sender_type"] = assistant_msg.sender_type
                        event["created_by"] = assistant_msg.created_by
                        event["created_at"] = assistant_msg.created_at.isoformat()
                    yield event
                elif et == "error":
                    had_error = True
                    yield {
                        "type": "ai_error",
                        "detail": str(sse.get("message", "AI error")),
                        "code": sse.get("code"),
                    }
                    return
        except HttpClientException as e:
            logger.error(
                "LLM stream failed: %s",
                str(e),
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "status_code": e.status_code,
                    "llm_stream_url": getattr(settings, stream_url_setting_name, ""),
                },
                exc_info=True,
            )
            fallback = await _build_and_save_complete()
            if fallback:
                yield fallback
                return
            raise LLMServiceException() from e

        if not received_complete and not had_error:
            fallback = await _build_and_save_complete()
            if fallback:
                yield fallback

    @staticmethod
    def _extract_document_question_complete(
            result: dict[str, Any],
            accumulated_answer: str,
            last_question: str,
            last_fragments: list[Any],
    ) -> tuple[str, str, list[Any]]:
        question = str(result.get("question", "")).strip() or last_question
        answer = str(result.get("answer", "")).strip() or accumulated_answer.strip()
        fragments = llm_client.normalize_fragments(result.get("fragments")) or last_fragments
        return question, answer, fragments

    @staticmethod
    def _extract_general_chat_complete(
            result: dict[str, Any],
            accumulated_answer: str,
            last_question: str,
            last_fragments: list[Any],
    ) -> tuple[str, str, list[Any]]:
        answer = str(result.get("answer", "")).strip() or accumulated_answer.strip()
        return "", answer, []

    @staticmethod
    def _extract_agent_complete(
            result: dict[str, Any],
            accumulated_answer: str,
            last_question: str,
            last_fragments: list[Any],
    ) -> tuple[str, str, list[Any]]:
        answer = ""
        messages = result.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                if isinstance(message, dict) and message.get("role") == "assistant":
                    answer = str(message.get("content", "")).strip()
                    break
        answer = answer or accumulated_answer.strip()
        fragments = llm_client.normalize_fragments(result.get("fragments")) or last_fragments
        return "", answer, fragments

    @staticmethod
    async def _get_chat_system_prompt(chat_id: int) -> str | None:
        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            return None
        prompt = getattr(chat, "system_prompt", None)
        return prompt or None

    def delete_message(self, user: AuthenticatedUser, chat_id: int, message_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({DELETE_MESSAGE}))
        self._require_access(chat_id, user.id)
        msg = message_repository.get_by_id_and_chat(message_id, chat_id)
        if msg is None:
            raise MessageNotFoundException()
        if not membership_repository.is_chat_owner(chat_id, user.id):
            raise MessageDeleteForbiddenException()
        msg.delete(deleted_by=user.id)
        logger.info("Message deleted.", extra={"chat_id": chat_id, "message_id": message_id, "user_id": user.id})

    def send_ephemeral_message(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            text: str,
    ) -> ArtifactMessage:
        AccessControl.require_permissions(user, frozenset({SEND_MESSAGE}))
        self._require_send_access(chat_id, user.id)
        return ArtifactMessage(
            message=text,
            sender_type=ArtifactMessage.SenderType.USER,
            created_by=user.id,
        )

    async def run_ephemeral_document_question(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            user_message: str,
    ) -> DocumentQuestionRunResult:
        await sync_to_async(self._require_access)(chat_id, user.id)
        messages = [{"role": "human", "content": user_message}]
        try:
            llm_out: DocumentQuestionResult = await llm_client.document_question(messages, user)
        except HttpClientException as e:
            logger.error(
                "LLM ephemeral document-question failed: %s",
                str(e),
                extra={"chat_id": chat_id, "user_id": user.id},
                exc_info=True,
            )
            raise LLMServiceException() from e
        return DocumentQuestionRunResult(
            question=llm_out.question,
            answer=llm_out.answer,
            fragments=llm_out.fragments,
            assistant_message=None,
        )

    async def run_ephemeral_ai_reply(
            self,
            mode: str,
            user: AuthenticatedUser,
            chat_id: int,
            user_message: str,
    ) -> DocumentQuestionRunResult:
        """Run a single non-persisted AI reply turn for the requested mode.

        Used by ephemeral chats: nothing is written to the database, only the
        LLM is invoked with the supplied message.
        """
        if mode == ChatAIMode.DOCUMENT_QUESTION:
            return await self.run_ephemeral_document_question(user, chat_id, user_message)

        await sync_to_async(self._require_access)(chat_id, user.id)
        messages = [{"role": "human", "content": user_message}]
        try:
            if mode == ChatAIMode.GENERAL_CHAT:
                system_prompt = await self._get_chat_system_prompt(chat_id)
                general = await llm_client.general_chat(
                    messages, user, system_prompt=system_prompt
                )
                return DocumentQuestionRunResult(
                    question="", answer=general.answer, fragments=[], assistant_message=None,
                )
            if mode == ChatAIMode.RAG_AGENT:
                rag = await llm_client.rag_agent(messages, user)
                return DocumentQuestionRunResult(
                    question="", answer=rag.answer, fragments=rag.fragments, assistant_message=None,
                )
            if mode == ChatAIMode.AGENT:
                agent = await llm_client.agent(messages, user)
                return DocumentQuestionRunResult(
                    question="", answer=agent.answer, fragments=agent.fragments, assistant_message=None,
                )
        except HttpClientException as e:
            logger.error(
                "LLM ephemeral %s failed: %s",
                mode,
                str(e),
                extra={"chat_id": chat_id, "user_id": user.id},
                exc_info=True,
            )
            raise LLMServiceException() from e

        return await self.run_ephemeral_document_question(user, chat_id, user_message)

    def _require_access(self, chat_id: int, user_id: int):
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user_id):
            raise MessageAccessDeniedException()
        return chat

    def _require_send_access(self, chat_id: int, user_id: int):
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        role = membership_repository.get_role(chat_id, user_id)
        if role is None:
            raise MessageAccessDeniedException()
        if role == "reader":
            raise ReaderCannotSendMessageException()
        if chat.is_locked:
            raise ChatLockedException()
        return chat


message_service = MessageService()
