import json
import logging
import re
import uuid

from fastapi import HTTPException, Request, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.checklist_service.checklist_prompt import RAG_QUERIES, SYSTEM_PROMPT
from app.application.services.checklist_service.exceptions.checklist_service_exceptions import ChecklistServiceException
from app.application.services.checklist_service.interfaces.checklist_service_interface import ChecklistServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.checklist.checklist_request import ChecklistGenerateRequest, ChecklistMode
from app.domain.dtos.checklist.checklist_response import ChecklistGenerateResponse, ChecklistItem
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
_MAX_ITEM_TEXT_CHARS = 500
_MAX_SECTION_CHARS = 200
_MAX_ITEMS = 200

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    ChecklistServiceException,
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
        request: ChecklistGenerateRequest,
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
    """Strip markdown code block fences and return the inner JSON string."""
    text = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    # Try to find first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _parse_items(raw_items: list) -> list[ChecklistItem]:
    items: list[ChecklistItem] = []
    for entry in raw_items[:_MAX_ITEMS]:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("text", "")).strip()[:_MAX_ITEM_TEXT_CHARS]
        if not text:
            continue
        items.append(
            ChecklistItem(
                id=str(uuid.uuid4()),
                section=str(entry.get("section", "General")).strip()[:_MAX_SECTION_CHARS] or "General",
                order=max(1, int(entry.get("order", 1))),
                text=text,
                is_checked=False,
                notes="",
            )
        )
    return items


def _fallback_items(raw: str) -> tuple[str, list[ChecklistItem]]:
    """When JSON parsing fails, create a single-section checklist from the raw text lines."""
    lines = [ln.strip().lstrip("•-*0123456789.) ") for ln in raw.splitlines() if ln.strip()]
    items = [
        ChecklistItem(
            id=str(uuid.uuid4()),
            section="Procedimiento",
            order=i + 1,
            text=ln[:_MAX_ITEM_TEXT_CHARS],
            is_checked=False,
            notes="",
        )
        for i, ln in enumerate(lines[:_MAX_ITEMS])
        if ln
    ]
    return "Checklist de procedimiento", items


def _parse_llm_output(raw: str) -> tuple[str, list[ChecklistItem]]:
    try:
        json_str = _extract_json(raw)
        data = json.loads(json_str)
        title = str(data.get("title", "Checklist")).strip()[:_MAX_TITLE_CHARS] or "Checklist"
        items = _parse_items(data.get("items", []))
        if not items:
            raise ValueError("No se encontraron ítems válidos en la respuesta.")
        return title, items
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_items(raw)


class ChecklistService(ChecklistServiceInterface):
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
        logger.info("ChecklistService initialized")

    async def generate(
            self,
            request: ChecklistGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ChecklistGenerateResponse:
        logger.info(
            "Checklist generation initiated",
            extra={"user_id": authenticated_user.id, "mode": request.mode},
        )

        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_CHECKLIST_GENERATE}),
        )

        try:
            fragments: list[FragmentResponse] = []

            if request.mode == ChecklistMode.RAG:
                fragments = await self._retrieve_fragments(request, authenticated_user)

            context_block = _build_context_block(fragments)
            llm_messages = _build_llm_messages(request, context_block)

            llm = await self._ollama_llm_facade.get_llm_base()
            raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)
            raw = raw.strip()

            if not raw:
                raise ChecklistServiceException(
                    "El modelo de lenguaje devolvió una respuesta vacía.",
                    status_code=502,
                )

            title, items = _parse_llm_output(raw)

            if not items:
                raise ChecklistServiceException(
                    "No se pudieron extraer ítems de la respuesta del modelo.",
                    status_code=502,
                )

            assistant_msg = Message(role=MessageRole.assistant, content=raw)
            updated_messages = [*request.messages, assistant_msg]

            logger.info(
                "Checklist generation completed",
                extra={
                    "user_id": authenticated_user.id,
                    "items_count": len(items),
                    "fragments_used": len(fragments),
                },
            )

            return ChecklistGenerateResponse(
                title=title,
                items=items,
                messages=updated_messages,
                fragments=fragments,
            )

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during checklist generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise ChecklistServiceException(
                "Error inesperado durante la generación de la checklist.",
                status_code=500,
            ) from e

    async def _retrieve_fragments(
            self,
            request: ChecklistGenerateRequest,
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


async def get_checklist_service(request: Request) -> ChecklistServiceInterface:
    try:
        return request.app.state.checklist_service
    except AttributeError:
        logger.error("ChecklistService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Checklist service is not available",
        )
