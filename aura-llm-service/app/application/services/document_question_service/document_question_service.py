import logging
from typing import Optional
from fastapi import HTTPException, Request, status
from langchain_core.messages import BaseMessage

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_question_service.document_question_prompt_builder import (
    DocumentQuestionPromptBuilder
)
from app.application.services.document_question_service.document_question_request_validator import (
    DocumentQuestionRequestValidator
)
from app.application.services.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings
)
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException
)
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question.document_question_response import DocumentQuestionResponse
from app.domain.dtos.message import Message
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface
)
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class DocumentQuestionService(DocumentQuestionServiceInterface):
    _KNOWN_EXCEPTIONS = (
        RequestValidationException,
        DocumentQuestionServiceException
    )

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            document_question_service_settings: Optional[DocumentQuestionServiceSettings] = None
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._llm_invoker = llm_invoker
        self._document_context_provider = document_context_provider
        self._settings = document_question_service_settings or DocumentQuestionServiceSettings()

        self._request_validator = DocumentQuestionRequestValidator(
            document_question_service_settings=self._settings
        )
        self._prompt_builder = DocumentQuestionPromptBuilder()

    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            user: AuthenticationResponse,
            authorization: Optional[str] = None
    ) -> DocumentQuestionResponse:
        logger.info("Document question execution initiated")

        try:
            self._request_validator.validate_request(
                document_question_request=document_question_request
            )

            context_fragments = await self._retrieve_context_fragments(
                question=document_question_request.question,
                authorization=authorization
            )

            answer = await self._generate_answer(
                question=document_question_request.question,
                context_fragments=context_fragments,
                history_messages=document_question_request.history_messages or []
            )

            logger.info("Document question execution completed")
            return DocumentQuestionResponse(answer=answer)

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during document question execution",
                extra={"error_type": type(e).__name__}
            )
            raise DocumentQuestionServiceException(
                "Unexpected error while processing the question"
            ) from e

    async def _retrieve_context_fragments(
            self,
            question: str,
            authorization: Optional[str]
    ) -> list[str]:
        logger.debug("Retrieving context fragments")

        try:
            fragments = await self._document_context_provider.retrieve_context_fragments_by_question(
                question=question,
                max_context_fragments=self._settings.max_context_fragments,
                authorization=authorization
            )

            logger.debug(
                "Context fragments retrieved",
                extra={"fragment_count": len(fragments)}
            )
            return fragments

        except DocumentQuestionServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to retrieve context fragments",
                extra={"error_type": type(e).__name__}
            )
            raise DocumentQuestionServiceException(
                "Error retrieving context fragments from the document service"
            ) from e

    async def _generate_answer(
            self,
            question: str,
            context_fragments: list[str],
            history_messages: list[Message]
    ) -> str:
        logger.debug("Generating answer")

        prompt = self._build_prompt(
            question=question,
            context_fragments=context_fragments,
            history_messages=history_messages
        )

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            answer = await self._llm_invoker.call_llm_content(llm=llm, llm_input=prompt)
        except DocumentQuestionServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to generate answer",
                extra={"error_type": type(e).__name__}
            )
            raise DocumentQuestionServiceException(
                "Error invoking the language model"
            ) from e

        if not answer or not answer.strip():
            logger.warning("LLM returned an empty answer")
            raise DocumentQuestionServiceException("The model did not generate a valid response")

        logger.debug("Answer generated successfully")
        return answer.strip()

    def _build_prompt(
            self,
            question: str,
            context_fragments: list[str],
            history_messages: list[Message]
    ) -> list[BaseMessage]:
        return self._prompt_builder.build_complete_prompt(
            system_prompt=self._settings.system_prompt,
            question=question,
            context_fragments=context_fragments,
            history_messages=history_messages
        )


async def get_document_question_service(request: Request) -> DocumentQuestionServiceInterface:
    try:
        return request.app.state.document_question_service
    except AttributeError:
        logger.error("DocumentQuestionService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentQuestionService is not available",
        )
