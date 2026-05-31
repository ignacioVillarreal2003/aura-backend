import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.report_service.exceptions.report_service_exceptions import ReportServiceException
from app.application.services.report_service.interfaces.report_service_interface import ReportServiceInterface
from app.application.services.report_service.report_templates import get_rag_queries, get_system_prompt
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message
from app.domain.dtos.report.report_request import ReportGenerateRequest, ReportMode
from app.domain.dtos.report.report_response import ReportGenerateResponse
from app.domain.field_limits import MAX_CONTENT_CHARS
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

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    ReportServiceException,
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
        system_prompt: str,
        request: ReportGenerateRequest,
        context_block: str,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

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


class ReportService(ReportServiceInterface):
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
        logger.info("ReportService initialized")

    async def generate(
            self,
            request: ReportGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ReportGenerateResponse:
        logger.info(
            "Report generation initiated",
            extra={
                "user_id": authenticated_user.id,
                "report_type": request.report_type,
                "mode": request.mode,
            },
        )

        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_REPORT_GENERATE}),
        )

        try:
            fragments: list[FragmentResponse] = []

            if request.mode == ReportMode.RAG:
                fragments = await self._retrieve_fragments(request, authenticated_user)

            system_prompt = get_system_prompt(request.report_type)
            context_block = _build_context_block(fragments)
            llm_messages = _build_llm_messages(system_prompt, request, context_block)

            llm = await self._ollama_llm_facade.get_llm_base()
            raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)
            content = raw.strip()

            if not content:
                raise ReportServiceException(
                    "El modelo de lenguaje devolvió una respuesta vacía.",
                    status_code=502,
                )

            if len(content) > MAX_CONTENT_CHARS:
                content = content[:MAX_CONTENT_CHARS]

            assistant_msg = Message(role=MessageRole.assistant, content=content)
            updated_messages = [*request.messages, assistant_msg]

            logger.info(
                "Report generation completed",
                extra={
                    "user_id": authenticated_user.id,
                    "report_type": request.report_type,
                    "fragments_used": len(fragments),
                },
            )

            return ReportGenerateResponse(
                report_type=request.report_type,
                content=content,
                messages=updated_messages,
                fragments=fragments,
            )

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during report generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise ReportServiceException(
                "Error inesperado durante la generación del informe.",
                status_code=500,
            ) from e

    async def _retrieve_fragments(
            self,
            request: ReportGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> list[FragmentResponse]:
        queries = get_rag_queries(request.report_type)
        last_content = request.messages[-1].content

        semantic_queries = [
            SemanticQuery(text=f"{last_content[:400]} {q}", max_fragments=3)
            for q in queries
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


async def get_report_service(request: Request) -> ReportServiceInterface:
    try:
        return request.app.state.report_service
    except AttributeError:
        logger.error("ReportService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Report service is not available",
        )
