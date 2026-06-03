import json
import logging
import re

from fastapi import HTTPException, Request, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.timeline_service.timeline_prompt import RAG_QUERIES, SYSTEM_PROMPT
from app.application.services.timeline_service.exceptions.timeline_service_exceptions import TimelineServiceException
from app.application.services.timeline_service.interfaces.timeline_service_interface import TimelineServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.timeline.timeline_request import TimelineGenerateRequest, TimelineMode
from app.domain.dtos.timeline.timeline_response import TimelineEvent, TimelineGenerateResponse
from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.dtos.question_context_fragments_request import (
    BM25Query,
    QuestionContextFragmentsRequest,
    RerankConfig,
    SemanticQuery,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_MAX_RAG_FRAGMENTS = 12
_MAX_CONTEXT_CHARS = 10_000
_MAX_TITLE_CHARS = 100
_MAX_SUMMARY_CHARS = 1_000
_MAX_EVENT_CHARS = 300
_MAX_DESCRIPTION_CHARS = 2_000
_MAX_LABEL_CHARS = 100
_MAX_EVENTS = 300

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    TimelineServiceException,
    UnauthorizedException,
)


def _build_context_block(fragments: list[FragmentResponse]) -> str:
    if not fragments:
        return ""
    parts: list[str] = ["=== CONTEXTO DOCUMENTAL RECUPERADO ==="]
    total = 0
    for i, frag in enumerate(fragments, 1):
        entry = f"\n[FRAGMENTO {i} — {frag.document.name}]\n{frag.content}"
        if total + len(entry) > _MAX_CONTEXT_CHARS:
            break
        parts.append(entry)
        total += len(entry)
    parts.append("=== FIN DE CONTEXTO ===")
    return "\n".join(parts)


def _build_llm_messages(
        request: TimelineGenerateRequest,
        context_block: str,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]

    history = list(request.messages)
    last_human = history[-1]
    prior = history[:-1]

    for msg in prior:
        if msg.role == MessageRole.human:
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == MessageRole.assistant:
            messages.append(AIMessage(content=msg.content))

    user_content = last_human.content
    if context_block:
        user_content = f"{user_content}\n\n{context_block}"

    messages.append(HumanMessage(content=user_content))
    return messages


def _extract_json(raw: str) -> str:
    text = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _clean(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _parse_events(raw_events: list) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for entry in raw_events[:_MAX_EVENTS]:
        if not isinstance(entry, dict):
            continue
        event_title = _clean(entry.get("event"), _MAX_EVENT_CHARS)
        if not event_title:
            continue
        occurred_at = entry.get("occurred_at")
        occurred_at = str(occurred_at).strip()[:64] if occurred_at else None
        events.append(
            TimelineEvent(
                event=event_title,
                description=_clean(entry.get("description"), _MAX_DESCRIPTION_CHARS),
                occurred_at=occurred_at or None,
                occurred_label=_clean(entry.get("occurred_label"), _MAX_LABEL_CHARS),
                source_document_id=None,
            )
        )
    return events


def _fallback_events(raw: str) -> tuple[str, str, list[TimelineEvent]]:
    lines = [ln.strip().lstrip("•-*0123456789.) ") for ln in raw.splitlines() if ln.strip()]
    events = [
        TimelineEvent(event=ln[:_MAX_EVENT_CHARS], description="", occurred_label="")
        for ln in lines[:_MAX_EVENTS]
        if ln
    ]
    return "Línea de tiempo", "", events


def _parse_llm_output(raw: str) -> tuple[str, str, list[TimelineEvent]]:
    try:
        data = json.loads(_extract_json(raw))
        title = _clean(data.get("title"), _MAX_TITLE_CHARS) or "Línea de tiempo"
        summary = _clean(data.get("summary"), _MAX_SUMMARY_CHARS)
        events = _parse_events(data.get("events", []))
        if not events:
            raise ValueError("No se encontraron eventos válidos en la respuesta.")
        return title, summary, events
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_events(raw)


class TimelineService(TimelineServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            authorizer: Authorizer,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._document_context_provider = document_context_provider
        self._authorizer = authorizer
        logger.info("TimelineService initialized")

    async def generate(
            self,
            request: TimelineGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> TimelineGenerateResponse:
        logger.info(
            "Timeline generation initiated",
            extra={"user_id": authenticated_user.id, "mode": request.mode},
        )

        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_TIMELINE_GENERATE}),
        )

        try:
            fragments: list[FragmentResponse] = []

            if request.mode == TimelineMode.RAG:
                fragments = await self._retrieve_fragments(request, authenticated_user)

            context_block = _build_context_block(fragments)
            llm_messages = _build_llm_messages(request, context_block)

            llm = await self._ollama_llm_facade.get_llm_base()
            raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)
            raw = raw.strip()

            if not raw:
                raise TimelineServiceException(
                    "El modelo de lenguaje devolvió una respuesta vacía.",
                    status_code=502,
                )

            title, summary, events = _parse_llm_output(raw)

            if not events:
                raise TimelineServiceException(
                    "No se pudieron extraer eventos de la respuesta del modelo.",
                    status_code=502,
                )

            assistant_msg = Message(role=MessageRole.assistant, content=raw)
            updated_messages = [*request.messages, assistant_msg]

            logger.info(
                "Timeline generation completed",
                extra={
                    "user_id": authenticated_user.id,
                    "events_count": len(events),
                    "fragments_used": len(fragments),
                },
            )

            return TimelineGenerateResponse(
                title=title,
                summary=summary,
                events=events,
                messages=updated_messages,
                fragments=fragments,
            )

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during timeline generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise TimelineServiceException(
                "Error inesperado durante la generación de la línea de tiempo.",
                status_code=500,
            ) from e

    async def _retrieve_fragments(
            self,
            request: TimelineGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> list[FragmentResponse]:
        last_content = request.messages[-1].content

        semantic_queries = [
            SemanticQuery(text=f"{last_content[:400]} {q}", max_fragments=2)
            for q in RAG_QUERIES
        ]
        bm25_queries = [
            BM25Query(text=last_content[:400], max_fragments=3),
        ]

        total_pool = sum(q.max_fragments for q in semantic_queries) + sum(q.max_fragments for q in bm25_queries)
        rerank_max = min(_MAX_RAG_FRAGMENTS, total_pool)

        retrieval_request = QuestionContextFragmentsRequest(
            chat_id=request.chat_id,
            semantic_queries=semantic_queries,
            bm25_queries=bm25_queries,
            rerank=RerankConfig(enabled=True, max_fragments=rerank_max),
            adjacent_chunks=1,
        )

        try:
            result = await self._document_context_provider.retrieve_context_fragments_by_question_request(
                authenticated_user=authenticated_user,
                request=retrieval_request,
            )
            return result.fragments[:_MAX_RAG_FRAGMENTS]
        except Exception:
            logger.warning(
                "Fragment retrieval failed; proceeding without context",
                extra={"user_id": authenticated_user.id},
            )
            return []


async def get_timeline_service(request: Request) -> TimelineServiceInterface:
    try:
        return request.app.state.timeline_service
    except AttributeError:
        logger.error("TimelineService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Timeline service is not available",
        )
