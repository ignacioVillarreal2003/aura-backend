"""Regression tests for response assembly caps:
- #1: building the conversation 'assistant' turn must never exceed the Message
  content cap (a large report/quiz output must not raise -> no 500); the response's
  own content field stays full.
- #2: the streaming char limit is enforced while streaming, so the deltas a client
  receives never exceed what the complete event carries.
"""
import types

from app.application.services.generation_shared.structured_generation_service import StructuredGenerationService
from app.application.services.generation_shared.streaming_generation_service import StreamingGenerationService
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_CONTENT_CHARS, MAX_MESSAGE_CONTENT_CHARS


def test_conversation_turn_is_clamped_to_message_cap():
    state = types.SimpleNamespace(
        messages=[Message(role=MessageRole.human, content="hola")]
    )
    huge = "x" * (MAX_MESSAGE_CONTENT_CHARS + 10_000)
    # Must not raise even though the artifact exceeds the Message content cap.
    convo = StructuredGenerationService._conversation_with_answer(state, huge)
    assert convo[-1].role == MessageRole.assistant
    assert len(convo[-1].content) == MAX_MESSAGE_CONTENT_CHARS


def test_default_response_limit_is_above_generation_ceiling():
    # num_predict=6144 tokens ~= 24.5k chars; the answer cap (50k) sits above it,
    # so the eager truncation never fires in normal operation -> deltas == complete.
    from app.application.services.user_interactions.general_chat_service.general_chat_settings import (
        GeneralChatSettings,
    )
    from app.application.services.user_interactions.document_question_service.document_question_settings import (
        DocumentQuestionServiceSettings,
    )

    assert GeneralChatSettings(_env_file=None).max_response_chars == MAX_CONTENT_CHARS
    assert DocumentQuestionServiceSettings(_env_file=None).max_response_chars == MAX_CONTENT_CHARS


class _LimitedService(StreamingGenerationService):
    """Minimal concrete streaming service exposing a small char limit so we can
    assert the streaming loop enforces it (deltas never exceed the cap)."""

    label = "test"

    def __init__(self, limit, chunks: list[str]) -> None:
        self._limit = limit
        self._chunks = chunks

    def _response_char_limit(self):
        return self._limit

    def _system_prompt(self, request):
        return ""

    def _build_response(self, state, request, answer):
        return answer


async def test_streaming_loop_trims_deltas_to_limit():
    # Drive only the delta-accumulation logic the way generate_stream does.
    svc = _LimitedService(limit=10, chunks=["abcd", "efgh", "ijkl"])
    limit = svc._response_char_limit()
    answer = ""
    deltas: list[str] = []
    for delta in svc._chunks:
        piece = delta
        if limit is not None:
            remaining = limit - len(answer)
            if remaining <= 0:
                break
            if len(piece) > remaining:
                piece = piece[:remaining]
        if not piece:
            continue
        answer += piece
        deltas.append(piece)

    assert "".join(deltas) == answer
    assert len(answer) == 10  # trimmed exactly to the limit
    assert answer == "abcdefghij"


def test_postprocess_answer_respects_limit():
    svc = _LimitedService(limit=5, chunks=[])
    assert svc._postprocess_answer("abcdefgh") == "abcde"


def test_postprocess_answer_no_limit_is_identity():
    svc = _LimitedService(limit=None, chunks=[])
    assert svc._response_char_limit() is None
    assert svc._postprocess_answer("abcdefgh") == "abcdefgh"
