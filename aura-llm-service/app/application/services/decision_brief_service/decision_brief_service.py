import json
import logging
import re

from fastapi import HTTPException, Request, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.decision_brief_service.decision_brief_prompt import RAG_QUERIES, SYSTEM_PROMPT
from app.application.services.decision_brief_service.exceptions.decision_brief_service_exceptions import (
    DecisionBriefServiceException,
)
from app.application.services.decision_brief_service.interfaces.decision_brief_service_interface import (
    DecisionBriefServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.decision_brief.decision_brief_request import DecisionBriefGenerateRequest, DecisionBriefMode
from app.domain.dtos.decision_brief.decision_brief_response import (
    DecisionBriefGenerateResponse,
    DecisionBriefOption,
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

_MAX_RAG_FRAGMENTS = 15
_MAX_CONTEXT_CHARS = 12_000
_MAX_TITLE_CHARS = 100
_MAX_NARRATIVE_CHARS = 4_000
_MAX_OPTION_TITLE_CHARS = 300
_MAX_OPTION_TEXT_CHARS = 2_000
_MAX_OPTIONS = 50

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    DecisionBriefServiceException,
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
        request: DecisionBriefGenerateRequest,
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


def _parse_options(raw_options: list) -> list[DecisionBriefOption]:
    options: list[DecisionBriefOption] = []
    for entry in raw_options[:_MAX_OPTIONS]:
        if not isinstance(entry, dict):
            continue
        title = _clean(entry.get("title"), _MAX_OPTION_TITLE_CHARS)
        if not title:
            continue
        options.append(
            DecisionBriefOption(
                title=title,
                description=_clean(entry.get("description"), _MAX_OPTION_TEXT_CHARS),
                pros=_clean(entry.get("pros"), _MAX_OPTION_TEXT_CHARS),
                cons=_clean(entry.get("cons"), _MAX_OPTION_TEXT_CHARS),
                is_recommended=bool(entry.get("is_recommended", False)),
            )
        )
    return options


def _fallback_options(raw: str) -> tuple[str, str, str, str, str, list[DecisionBriefOption]]:
    lines = [ln.strip().lstrip("•-*0123456789.) ") for ln in raw.splitlines() if ln.strip()]
    options = [
        DecisionBriefOption(title=ln[:_MAX_OPTION_TITLE_CHARS])
        for ln in lines[:_MAX_OPTIONS]
        if ln
    ]
    return "Brief de decisión", "", "", "", "", options


def _parse_llm_output(raw: str):
    try:
        data = json.loads(_extract_json(raw))
        title = _clean(data.get("title"), _MAX_TITLE_CHARS) or "Brief de decisión"
        problem = _clean(data.get("problem"), _MAX_NARRATIVE_CHARS)
        context = _clean(data.get("context"), _MAX_NARRATIVE_CHARS)
        risks = _clean(data.get("risks"), _MAX_NARRATIVE_CHARS)
        recommendation = _clean(data.get("recommendation"), _MAX_NARRATIVE_CHARS)
        options = _parse_options(data.get("options", []))
        if not options:
            raise ValueError("No se encontraron opciones válidas en la respuesta.")
        return title, problem, context, risks, recommendation, options
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_options(raw)


class DecisionBriefService(DecisionBriefServiceInterface):
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
        logger.info("DecisionBriefService initialized")

    async def generate(
            self,
            request: DecisionBriefGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DecisionBriefGenerateResponse:
        logger.info(
            "Decision-brief generation initiated",
            extra={"user_id": authenticated_user.id, "mode": request.mode},
        )

        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DECISION_BRIEF_GENERATE}),
        )

        try:
            fragments: list[FragmentResponse] = []

            if request.mode == DecisionBriefMode.RAG:
                fragments = await self._retrieve_fragments(request, authenticated_user)

            context_block = _build_context_block(fragments)
            llm_messages = _build_llm_messages(request, context_block)

            llm = await self._ollama_llm_facade.get_llm_base()
            raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)
            raw = raw.strip()

            if not raw:
                raise DecisionBriefServiceException(
                    "El modelo de lenguaje devolvió una respuesta vacía.",
                    status_code=502,
                )

            title, problem, context, risks, recommendation, options = _parse_llm_output(raw)

            if not options:
                raise DecisionBriefServiceException(
                    "No se pudieron extraer opciones de la respuesta del modelo.",
                    status_code=502,
                )

            assistant_msg = Message(role=MessageRole.assistant, content=raw)
            updated_messages = [*request.messages, assistant_msg]

            logger.info(
                "Decision-brief generation completed",
                extra={
                    "user_id": authenticated_user.id,
                    "options_count": len(options),
                    "fragments_used": len(fragments),
                },
            )

            return DecisionBriefGenerateResponse(
                title=title,
                problem=problem,
                context=context,
                risks=risks,
                recommendation=recommendation,
                options=options,
                messages=updated_messages,
                fragments=fragments,
            )

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during decision-brief generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise DecisionBriefServiceException(
                "Error inesperado durante la generación del brief de decisión.",
                status_code=500,
            ) from e

    async def _retrieve_fragments(
            self,
            request: DecisionBriefGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> list[FragmentResponse]:
        last_content = request.messages[-1].content

        semantic_queries = [
            SemanticQuery(text=f"{last_content[:400]} {q}", max_fragments=3)
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


async def get_decision_brief_service(request: Request) -> DecisionBriefServiceInterface:
    try:
        return request.app.state.decision_brief_service
    except AttributeError:
        logger.error("DecisionBriefService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Decision-brief service is not available",
        )
