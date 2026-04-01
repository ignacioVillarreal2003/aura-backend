import logging
from typing import Optional, Any

from fastapi import HTTPException, Request, status
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.support.fragment_enrich_service.exceptions.fragment_enrich_service_exceptions import (
    FragmentEnrichServiceException,
)
from app.application.services.support.fragment_enrich_service.fragment_enrich_settings import FragmentEnrichServiceSettings
from app.application.services.support.fragment_enrich_service.interfaces.fragment_enrich_service_interface import (
    FragmentEnrichServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.support.fragment_enrich.enrich_fragment_request import EnrichFragmentRequest
from app.domain.dtos.support.fragment_enrich.enrich_fragment_response import EnrichFragmentResponse
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_ENRICH_SYSTEM = """Eres un asistente que enriquece fragmentos de texto de documentos.
Responde únicamente con un objeto JSON válido, sin texto antes ni después, sin bloques markdown.
El JSON debe tener exactamente estas claves:
- "summary": string con un resumen breve del fragmento en español
- "entities": objeto cuyas claves son nombres de entidades y los valores son strings o listas (ej. personas, fechas, montos)
- "topics": array de strings con temas principales"""


_ENRICH_HUMAN = """Fragmento de texto (puede estar truncado):
{content}

Devuelve solo el JSON."""


class FragmentEnrichService(FragmentEnrichServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            llm_invoker: OllamaLLMInvokerInterface,
            settings: Optional[FragmentEnrichServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._llm_invoker = llm_invoker
        self._settings = settings or FragmentEnrichServiceSettings()

    async def enrich_fragment(
            self,
            request: EnrichFragmentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> EnrichFragmentResponse:
        content = request.content
        if len(content) > self._settings.max_content_chars:
            logger.info(
                "Truncating fragment content for enrichment",
                extra={
                    "original_len": len(content),
                    "max_chars": self._settings.max_content_chars,
                    "user_id": authenticated_user.id,
                },
            )
            content = content[: self._settings.max_content_chars]

        llm_input = [
            SystemMessage(content=_ENRICH_SYSTEM),
            HumanMessage(content=_ENRICH_HUMAN.format(content=content)),
        ]

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            raw = await self._llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except FragmentEnrichServiceException:
            raise
        except Exception as e:
            logger.exception(
                "LLM invocation failed during fragment enrichment",
                extra={"user_id": authenticated_user.id},
            )
            raise FragmentEnrichServiceException(
                "El modelo de lenguaje no pudo enriquecer el fragmento."
            ) from e

        if not raw or not raw.strip():
            raise FragmentEnrichServiceException(
                "El modelo no devolvió una respuesta válida.",
                status_code=502,
            )

        try:
            data = self.parse_json_object_from_llm_text(raw)
            return EnrichFragmentResponse.model_validate(data)
        except Exception as e:
            logger.warning(
                "Failed to parse enrichment JSON from LLM",
                extra={"user_id": authenticated_user.id, "error": str(e)},
            )
            raise FragmentEnrichServiceException(
                "La respuesta del modelo no tiene el formato JSON esperado.",
                status_code=502,
            ) from e

    def parse_json_object_from_llm_text(self, text: str) -> dict[str, Any]:
        s = text.strip()
        if s.startswith("```"):
            lines = s.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            s = "\n".join(lines).strip()

        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            start = s.find("{")
            end = s.rfind("}")
            if start < 0 or end <= start:
                logger.warning("Could not locate JSON object in LLM output")
                raise
            parsed = json.loads(s[start:end + 1])

        if not isinstance(parsed, dict):
            raise TypeError(f"Expected JSON object, got {type(parsed).__name__}")
        return parsed

async def get_fragment_enrich_service(request: Request) -> FragmentEnrichServiceInterface:
    try:
        return request.app.state.fragment_enrich_service
    except AttributeError:
        logger.error("FragmentEnrichService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FragmentEnrichService is not available",
        )
