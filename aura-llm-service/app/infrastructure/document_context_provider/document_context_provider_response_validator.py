import logging
from typing import List

from app.infrastructure.document_context_provider.document_context_provider_configuration import \
    DocumentContextProviderConfiguration
from app.infrastructure.document_context_provider.dtos.context_fragments_response import ContextFragmentsResponse
from app.infrastructure.document_context_provider.exceptions.document_context_provider_exception import \
    DocumentContextProviderError

logger = logging.getLogger(__name__)


class DocumentContextProviderResponseValidator:
    def __init__(self,
                 document_context_provider_configuration: DocumentContextProviderConfiguration) -> None:
        self._document_context_provider_configuration = document_context_provider_configuration

    def validate_and_parse_response(self,
                                    context_fragments_response: ContextFragmentsResponse) -> List[str]:
        logger.debug("Starting request validation")

        context_fragments = self._validate_context_fragments(context_fragments_response)

        logger.debug("Request validation completed successfully")

        return context_fragments

    def _validate_context_fragments(self,
                                    context_fragments_response: ContextFragmentsResponse) -> List[str]:
        try:
            context_fragments_response_model = ContextFragmentsResponse.model_validate(context_fragments_response)
            context_fragments = context_fragments_response_model.context_fragments

            logger.debug("Response parsed successfully")

        except Exception as e:
            logger.error(
                "Failed to parse response",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise DocumentContextProviderError(
                "El servicio de contexto retornó una respuesta con formato inválido. "
                "No se pudo procesar la estructura de datos recibida."
            ) from e

        self._apply_security_limits(
            context_fragments=context_fragments
        )

        return context_fragments

    def _apply_security_limits(self,
                               context_fragments: List[str]) -> List[str]:
        validated_context_fragments: List[str] = []
        total_chars = 0
        skipped_oversized = 0
        truncated_count = 0

        max_to_process = min(
            len(context_fragments),
            self._document_context_provider_configuration.max_fragments_total
        )

        if len(context_fragments) > max_to_process:
            logger.warning(
                "Response exceeds maximum allowed fragments, truncating",
                extra={
                    "received_fragments": len(context_fragments),
                    "max_allowed": self._document_context_provider_configuration.max_fragments_total
                }
            )

        for idx, context_fragment in enumerate(context_fragments[:max_to_process]):
            context_fragment_len = len(context_fragment)

            if context_fragment_len > self._document_context_provider_configuration.max_chars_per_fragment:
                if self._document_context_provider_configuration.truncate_fragments_exceeding_max_chars:
                    context_fragment = context_fragment[:self._document_context_provider_configuration.max_chars_per_fragment]
                    truncated_count += 1

                    logger.debug("Fragment truncated due to size limit")
                else:
                    skipped_oversized += 1

                    logger.warning("Fragment skipped due to excessive size")
                    continue

            if total_chars + len(context_fragment) > self._document_context_provider_configuration.max_total_chars:
                logger.warning("Total response size limit reached, stopping collection")
                break

            validated_context_fragments.append(context_fragment)
            total_chars += len(context_fragment)

        logger.info("Fragment security validation completed")

        return validated_context_fragments