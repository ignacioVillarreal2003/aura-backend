import json
import logging
from typing import Optional, Any

from fastapi import HTTPException, Request, status
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.document_classify_service.document_classify_settings import (
    DocumentClassifyServiceSettings,
)
from app.application.services.document_classify_service.exceptions.document_classify_service_exceptions import (
    DocumentClassifyServiceException,
)
from app.application.services.document_classify_service.interfaces.document_classify_service_interface import (
    DocumentClassifyServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.document_classify.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_CLASSIFY_SYSTEM = """Eres un asistente que clasifica documentos legales o administrativos.
Responde únicamente con un objeto JSON válido, sin texto antes ni después, sin bloques markdown.
El JSON debe tener exactamente estas claves:
- "type": uno de estos strings exactos: manual, informe, orden, doctrina, otro
- "category": string corto con la categoría temática (ej. "laboral", "tributario")
- "description": string con una descripción breve del documento en español"""


_CLASSIFY_HUMAN = """Nombre del documento: {document_name}

Contenido (puede estar truncado):
{content}

Devuelve solo el JSON."""


class DocumentClassifyService(DocumentClassifyServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            llm_invoker: OllamaLLMInvokerInterface,
            authorizer: Authorizer,
            settings: Optional[DocumentClassifyServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._llm_invoker = llm_invoker
        self._authorizer = authorizer
        self._settings = settings or DocumentClassifyServiceSettings()

    async def classify_document(
            self,
            classify_document_request: ClassifyDocumentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ClassifyDocumentResponse:
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_CLASSIFY}),
        )
        content = classify_document_request.content
        if len(content) > self._settings.max_content_chars:
            logger.info(
                "Truncating document content for classification",
                extra={
                    "original_len": len(content),
                    "max_chars": self._settings.max_content_chars,
                    "user_id": authenticated_user.id,
                },
            )
            content = content[: self._settings.max_content_chars]

        llm_input = [
            SystemMessage(content=_CLASSIFY_SYSTEM),
            HumanMessage(
                content=_CLASSIFY_HUMAN.format(
                    document_name=classify_document_request.document_name,
                    content=content,
                )
            ),
        ]

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            raw = await self._llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except DocumentClassifyServiceException:
            raise
        except Exception as e:
            logger.exception(
                "LLM invocation failed during document classification",
                extra={"user_id": authenticated_user.id},
            )
            raise DocumentClassifyServiceException(
                "El modelo de lenguaje no pudo clasificar el documento."
            ) from e

        if not raw or not raw.strip():
            raise DocumentClassifyServiceException(
                "El modelo no devolvió una respuesta válida.",
                status_code=502,
            )

        try:
            data = self.parse_json_object_from_llm_text(raw)
            return ClassifyDocumentResponse.model_validate(data)
        except Exception as e:
            logger.warning(
                "Failed to parse classification JSON from LLM",
                extra={"user_id": authenticated_user.id, "error": str(e)},
            )
            raise DocumentClassifyServiceException(
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


async def get_document_classify_service(request: Request) -> DocumentClassifyServiceInterface:
    try:
        return request.app.state.document_classify_service
    except AttributeError:
        logger.error("DocumentClassifyService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentClassifyService is not available",
        )
