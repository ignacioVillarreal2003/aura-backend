import json
import logging
from typing import Optional

from fastapi import HTTPException, Request, status

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_question_service.document_question_prompt_builder import (
    DocumentQuestionPromptBuilder,
)
from app.application.services.document_question_service.document_question_request_validator import (
    DocumentQuestionRequestValidator,
)
from app.application.services.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface,
)
from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question.document_question_response import DocumentQuestionResponse
from app.domain.dtos.message import Message
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class DocumentQuestionService(DocumentQuestionServiceInterface):
    _KNOWN_EXCEPTIONS = (
        RequestValidationException,
        DocumentQuestionServiceException,
    )

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            document_question_service_settings: Optional[DocumentQuestionServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._llm_invoker = llm_invoker
        self._document_context_provider = document_context_provider
        self._settings = document_question_service_settings or DocumentQuestionServiceSettings()

        self._request_validator = DocumentQuestionRequestValidator(
            document_question_service_settings=self._settings
        )
        self._prompt_builder = DocumentQuestionPromptBuilder()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            user: AuthenticationResponse,
            authorization: Optional[str] = None,
    ) -> DocumentQuestionResponse:
        logger.info("Document question execution initiated")

        try:
            # Step 1 – Validate
            self._request_validator.validate_request(
                document_question_request=document_question_request
            )

            history = document_question_request.history_messages or []
            original_question = document_question_request.question

            # Step 2 – Query rewrite (graceful degradation on failure)
            effective_query = await self._rewrite_query(
                question=original_question,
                history_messages=history,
            )

            # Step 3 – Retrieve context fragments using the optimised query
            fragments = await self._retrieve_context_fragments(
                question=effective_query,
                authorization=authorization,
            )

            # Step 4 – Conditional reranking
            # Only pays the extra LLM call when we have more fragments than
            # the threshold — below it the latency gain is not worth it.
            if len(fragments) > self._settings.rerank_threshold:
                fragments = await self._select_context(
                    query=effective_query,
                    fragments=fragments,
                )

            # Step 5 – Generate (fallback when no usable context)
            if not fragments:
                answer = await self._generate_fallback(question=original_question)
            else:
                answer = await self._generate_answer(
                    question=original_question,
                    context_fragments=fragments,
                    history_messages=history,
                )

            logger.info("Document question execution completed")
            return DocumentQuestionResponse(answer=answer)

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during document question execution",
                extra={"error_type": type(e).__name__},
            )
            raise DocumentQuestionServiceException(
                "Unexpected error while processing the question"
            ) from e

    # ------------------------------------------------------------------
    # Step 2 – Query rewrite
    # ------------------------------------------------------------------

    async def _rewrite_query(
            self,
            question: str,
            history_messages: list[Message],
    ) -> str:
        """Rewrites the user's question into an optimised vector-search query.

        Falls back to the original question on any failure so the pipeline
        always continues.
        """
        if not self._settings.query_rewrite_enabled:
            return question

        try:
            prompt = self._prompt_builder.build_query_rewrite_prompt(
                question=question,
                history_messages=history_messages,
            )
            llm = await self._ollama_llm_facade.get_llm_base()
            rewritten = await self._llm_invoker.call_llm_content(llm=llm, llm_input=prompt)

            if rewritten and rewritten.strip():
                logger.debug(
                    "Query rewritten",
                    extra={
                        "original": question,
                        "rewritten": rewritten.strip(),
                    },
                )
                return rewritten.strip()

            logger.warning("Query rewrite returned empty result, using original")
            return question

        except Exception:
            logger.warning(
                "Query rewrite failed, falling back to original question",
                exc_info=True,
            )
            return question

    # ------------------------------------------------------------------
    # Step 3 – Context retrieval
    # ------------------------------------------------------------------

    async def _retrieve_context_fragments(
            self,
            question: str,
            authorization: Optional[str],
    ) -> list[str]:
        logger.debug("Retrieving context fragments")

        try:
            fragments = await self._document_context_provider.retrieve_context_fragments_by_question(
                question=question,
                max_context_fragments=self._settings.max_context_fragments,
                authorization=authorization,
            )
            logger.debug(
                "Context fragments retrieved",
                extra={"fragment_count": len(fragments)},
            )
            return fragments

        except DocumentQuestionServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to retrieve context fragments",
                extra={"error_type": type(e).__name__},
            )
            raise DocumentQuestionServiceException(
                "Error retrieving context fragments from the document service"
            ) from e

    # ------------------------------------------------------------------
    # Step 4 – Context selection / reranking
    # ------------------------------------------------------------------

    async def _select_context(
            self,
            query: str,
            fragments: list[str],
    ) -> list[str]:
        """Uses the LLM to pick the most relevant subset of fragments.

        Parses the expected JSON-array-of-indices response.  Falls back to
        the original fragment list on any parsing or invocation error so the
        pipeline never stalls.
        """
        logger.debug(
            "Running context selection",
            extra={
                "total_fragments": len(fragments),
                "max_reranked": self._settings.max_reranked_fragments,
            },
        )

        try:
            prompt = self._prompt_builder.build_context_selection_prompt(
                query=query,
                fragments=fragments,
                max_fragments=self._settings.max_reranked_fragments,
            )
            llm = await self._ollama_llm_facade.get_llm_base()
            raw_response = await self._llm_invoker.call_llm_content(llm=llm, llm_input=prompt)

            selected = self._parse_selection_indices(
                raw=raw_response,
                max_index=len(fragments) - 1,
            )

            if not selected:
                logger.warning("Context selection returned no valid indices, keeping all fragments")
                return fragments

            logger.debug(
                "Context selection complete",
                extra={"selected_indices": selected},
            )
            return [fragments[i] for i in selected]

        except Exception:
            logger.warning(
                "Context selection failed, keeping all retrieved fragments",
                exc_info=True,
            )
            return fragments

    @staticmethod
    def _parse_selection_indices(raw: str, max_index: int) -> list[int]:
        """Parses a JSON array of integers from the LLM response.

        Strips surrounding text/markdown fences so minor formatting
        deviations don't break the parse.
        """
        if not raw:
            return []

        # Extract the first [...] block in the response
        start = raw.find("[")
        end = raw.rfind("]")

        if start == -1 or end == -1 or end <= start:
            logger.warning("No JSON array found in context selection response", extra={"raw": raw})
            return []

        try:
            indices = json.loads(raw[start: end + 1])
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from context selection response", extra={"raw": raw})
            return []

        if not isinstance(indices, list):
            return []

        valid = [
            int(i)
            for i in indices
            if isinstance(i, (int, float)) and 0 <= int(i) <= max_index
        ]

        return list(dict.fromkeys(valid))  # deduplicate preserving order

    # ------------------------------------------------------------------
    # Step 5a – Answer generation
    # ------------------------------------------------------------------

    async def _generate_answer(
            self,
            question: str,
            context_fragments: list[str],
            history_messages: list[Message],
    ) -> str:
        logger.debug("Generating answer")

        prompt = self._prompt_builder.build_generation_prompt(
            question=question,
            context_fragments=context_fragments,
            history_messages=history_messages,
            system_prompt=self._settings.system_prompt,
        )

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            answer = await self._llm_invoker.call_llm_content(llm=llm, llm_input=prompt)
        except DocumentQuestionServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to generate answer",
                extra={"error_type": type(e).__name__},
            )
            raise DocumentQuestionServiceException(
                "Error invoking the language model"
            ) from e

        if not answer or not answer.strip():
            logger.warning("LLM returned an empty answer")
            raise DocumentQuestionServiceException("The model did not generate a valid response")

        logger.debug("Answer generated successfully")
        return answer.strip()

    # ------------------------------------------------------------------
    # Step 5b – Fallback generation
    # ------------------------------------------------------------------

    async def _generate_fallback(self, question: str) -> str:
        """Generates a formal fallback response when no context was found."""
        logger.info("No context fragments found, generating fallback response")

        prompt = self._prompt_builder.build_fallback_prompt(
            question=question,
            system_prompt=self._settings.system_prompt,
        )

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            answer = await self._llm_invoker.call_llm_content(llm=llm, llm_input=prompt)

            if answer and answer.strip():
                return answer.strip()

        except Exception:
            logger.warning("Fallback generation failed, returning static message", exc_info=True)

        # Last-resort static message
        return (
            "No se encontró información relevante en la base documental para responder su consulta. "
            "Por favor, reformule su pregunta o consulte directamente la documentación disponible."
        )


# ------------------------------------------------------------------
# FastAPI dependency
# ------------------------------------------------------------------

async def get_document_question_service(request: Request) -> DocumentQuestionServiceInterface:
    try:
        return request.app.state.document_question_service
    except AttributeError:
        logger.error("DocumentQuestionService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentQuestionService is not available",
        )
