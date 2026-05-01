import json
import logging
from typing import Optional
from fastapi import HTTPException, Request, status
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.fragment_enrich_service.exceptions.fragment_enrich_service_exceptions import (
    FragmentEnrichServiceException,
)
from app.application.services.fragment_enrich_service.fragment_enrich_prompt import (
    HUMAN_PROMPT,
    SYSTEM_PROMPT,
)
from app.application.services.fragment_enrich_service.fragment_enrich_settings import FragmentEnrichServiceSettings
from app.application.services.fragment_enrich_service.fragment_enrich_state import FragmentEnrichState
from app.application.services.fragment_enrich_service.interfaces.fragment_enrich_service_interface import (
    FragmentEnrichServiceInterface,
)
from app.application.utils.llm_json_parser import parse_json_object
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.fragment_enrich.enrich_fragment_request import EnrichFragmentRequest
from app.domain.dtos.fragment_enrich.enrich_fragment_response import EnrichFragmentResponse
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    FragmentEnrichServiceException,
    UnauthorizedException,
)


class FragmentEnrichService(FragmentEnrichServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            authorizer: Authorizer,
            fragment_enrich_service_settings: Optional[FragmentEnrichServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._authorizer = authorizer
        self._settings = fragment_enrich_service_settings or FragmentEnrichServiceSettings()

    async def enrich_fragment(
            self,
            enrich_fragment_request: EnrichFragmentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> EnrichFragmentResponse:
        log_extra = {
            "user_id": authenticated_user.id,
            "content_len": len(enrich_fragment_request.content),
        }
        logger.info("Fragment enrichment initiated", extra=log_extra)
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_FRAGMENT_ENRICH}),
        )
        try:
            state = self._build_state(enrich_fragment_request, authenticated_user)
            result = await self._run(state)
            logger.info("Fragment enrichment completed", extra=log_extra)
            return result
        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during fragment enrichment",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise FragmentEnrichServiceException("Error inesperado al enriquecer el fragmento.") from e

    def _build_state(
            self,
            enrich_fragment_request: EnrichFragmentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> FragmentEnrichState:
        content = self._truncate_content(enrich_fragment_request.content, authenticated_user.id)
        return FragmentEnrichState(authenticated_user=authenticated_user, content=content)

    async def _run(self, state: FragmentEnrichState) -> EnrichFragmentResponse:
        raw = await self._invoke_llm(state)
        return self._parse_response(raw, state.authenticated_user.id)

    def _truncate_content(self, content: str, user_id: int) -> str:
        if len(content) <= self._settings.max_content_chars:
            return content
        logger.info(
            "Truncating fragment content for enrichment",
            extra={
                "original_len": len(content),
                "max_chars": self._settings.max_content_chars,
                "user_id": user_id,
            },
        )
        return content[: self._settings.max_content_chars]

    async def _invoke_llm(self, state: FragmentEnrichState) -> str:
        user_id = state.authenticated_user.id
        llm_input = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=HUMAN_PROMPT.format(content=state.content)),
        ]
        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            return await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except LLMInvocationError as e:
            logger.warning(
                "LLM invocation failed during fragment enrichment",
                extra={"user_id": user_id, "error_type": type(e).__name__},
            )
            raise FragmentEnrichServiceException(
                "El modelo de lenguaje no pudo enriquecer el fragmento.",
                status_code=502,
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected LLM error during fragment enrichment",
                extra={"user_id": user_id, "error_type": type(e).__name__},
            )
            raise FragmentEnrichServiceException(
                "El modelo de lenguaje no pudo enriquecer el fragmento.",
                status_code=502,
            ) from e

    def _parse_response(self, raw: str, user_id: int) -> EnrichFragmentResponse:
        try:
            data = parse_json_object(raw)
            return EnrichFragmentResponse.model_validate(data)
        except (ValidationError, json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "Failed to parse enrichment JSON from LLM",
                extra={"user_id": user_id, "error_type": type(e).__name__, "error": str(e)},
            )
            raise FragmentEnrichServiceException(
                "La respuesta del modelo no tiene el formato JSON esperado.",
                status_code=502,
            ) from e


async def get_fragment_enrich_service(request: Request) -> FragmentEnrichServiceInterface:
    try:
        return request.app.state.fragment_enrich_service
    except AttributeError:
        logger.error("FragmentEnrichService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FragmentEnrichService is not available",
        )
