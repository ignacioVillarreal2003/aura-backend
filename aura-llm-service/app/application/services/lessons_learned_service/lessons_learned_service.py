import json
import logging
import re

from fastapi import HTTPException, Request, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.lessons_learned_service.lessons_learned_prompt import RAG_QUERIES, SYSTEM_PROMPT
from app.application.services.lessons_learned_service.exceptions.lessons_learned_service_exceptions import (
    LessonsLearnedServiceException,
)
from app.application.services.lessons_learned_service.interfaces.lessons_learned_service_interface import (
    LessonsLearnedServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.lessons_learned.lessons_learned_request import LessonsLearnedGenerateRequest, LessonsLearnedMode
from app.domain.dtos.lessons_learned.lessons_learned_response import (
    LessonCategory,
    LessonsLearnedGenerateResponse,
    LessonsLearnedItem,
)
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
_MAX_NARRATIVE_CHARS = 4_000
_MAX_OBSERVATION_CHARS = 2_000
_MAX_ITEMS = 300

_VALID_CATEGORIES = {c.value for c in LessonCategory}

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    LessonsLearnedServiceException,
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
        request: LessonsLearnedGenerateRequest,
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


def _parse_items(raw_items: list) -> list[LessonsLearnedItem]:
    items: list[LessonsLearnedItem] = []
    for entry in raw_items[:_MAX_ITEMS]:
        if not isinstance(entry, dict):
            continue
        observation = _clean(entry.get("observation"), _MAX_OBSERVATION_CHARS)
        if not observation:
            continue
        category = str(entry.get("category", LessonCategory.SUSTAIN)).strip().lower()
        if category not in _VALID_CATEGORIES:
            category = LessonCategory.SUSTAIN
        items.append(
            LessonsLearnedItem(
                category=category,
                observation=observation,
                discussion=_clean(entry.get("discussion"), _MAX_OBSERVATION_CHARS),
                recommendation=_clean(entry.get("recommendation"), _MAX_OBSERVATION_CHARS),
            )
        )
    return items


def _fallback_items(raw: str) -> tuple[str, str, str, str, str, list[LessonsLearnedItem]]:
    lines = [ln.strip().lstrip("•-*0123456789.) ") for ln in raw.splitlines() if ln.strip()]
    items = [
        LessonsLearnedItem(category=LessonCategory.IMPROVE, observation=ln[:_MAX_OBSERVATION_CHARS])
        for ln in lines[:_MAX_ITEMS]
        if ln
    ]
    return "Lecciones aprendidas", "", "", "", "", items


def _parse_llm_output(raw: str):
    try:
        data = json.loads(_extract_json(raw))
        title = _clean(data.get("title"), _MAX_TITLE_CHARS) or "Lecciones aprendidas"
        context = _clean(data.get("context"), _MAX_NARRATIVE_CHARS)
        what_went_well = _clean(data.get("what_went_well"), _MAX_NARRATIVE_CHARS)
        what_failed = _clean(data.get("what_failed"), _MAX_NARRATIVE_CHARS)
        recommendations = _clean(data.get("recommendations"), _MAX_NARRATIVE_CHARS)
        items = _parse_items(data.get("items", []))
        if not items:
            raise ValueError("No se encontraron lecciones válidas en la respuesta.")
        return title, context, what_went_well, what_failed, recommendations, items
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_items(raw)


class LessonsLearnedService(LessonsLearnedServiceInterface):
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
        logger.info("LessonsLearnedService initialized")

    async def generate(
            self,
            request: LessonsLearnedGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> LessonsLearnedGenerateResponse:
        logger.info(
            "Lessons-learned generation initiated",
            extra={"user_id": authenticated_user.id, "mode": request.mode},
        )

        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_LESSONS_LEARNED_GENERATE}),
        )

        try:
            fragments: list[FragmentResponse] = []

            if request.mode == LessonsLearnedMode.RAG:
                fragments = await self._retrieve_fragments(request, authenticated_user)

            context_block = _build_context_block(fragments)
            llm_messages = _build_llm_messages(request, context_block)

            llm = await self._ollama_llm_facade.get_llm_base()
            raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)
            raw = raw.strip()

            if not raw:
                raise LessonsLearnedServiceException(
                    "El modelo de lenguaje devolvió una respuesta vacía.",
                    status_code=502,
                )

            title, context, what_went_well, what_failed, recommendations, items = _parse_llm_output(raw)

            if not items:
                raise LessonsLearnedServiceException(
                    "No se pudieron extraer lecciones de la respuesta del modelo.",
                    status_code=502,
                )

            assistant_msg = Message(role=MessageRole.assistant, content=raw)
            updated_messages = [*request.messages, assistant_msg]

            logger.info(
                "Lessons-learned generation completed",
                extra={
                    "user_id": authenticated_user.id,
                    "items_count": len(items),
                    "fragments_used": len(fragments),
                },
            )

            return LessonsLearnedGenerateResponse(
                title=title,
                context=context,
                what_went_well=what_went_well,
                what_failed=what_failed,
                recommendations=recommendations,
                items=items,
                messages=updated_messages,
                fragments=fragments,
            )

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during lessons-learned generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise LessonsLearnedServiceException(
                "Error inesperado durante la generación de las lecciones aprendidas.",
                status_code=500,
            ) from e

    async def _retrieve_fragments(
            self,
            request: LessonsLearnedGenerateRequest,
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


async def get_lessons_learned_service(request: Request) -> LessonsLearnedServiceInterface:
    try:
        return request.app.state.lessons_learned_service
    except AttributeError:
        logger.error("LessonsLearnedService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lessons-learned service is not available",
        )
