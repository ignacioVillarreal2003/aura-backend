from app.infrastructure.http.document_context_provider.document_context_provider_settings import (
    DocumentContextProviderSettings
)
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
from app.infrastructure.http.document_context_provider.exceptions.document_context_provider_exception import (
    DocumentContextProviderError
)


class DocumentContextProviderValidator:
    def __init__(
            self,
            document_context_provider_settings: DocumentContextProviderSettings) -> None:
        self._settings = document_context_provider_settings

    def validate_question(
            self,
            question: str
    ) -> None:
        if not question or not question.strip():
            raise DocumentContextProviderError(
                "The question must be a non-empty string.",
                status_code=400
            )
        if len(question) > self._settings.max_question_chars:
            raise DocumentContextProviderError(
                f"The question exceeds the maximum allowed length "
                f"of {self._settings.max_question_chars:,} characters.",
                status_code=400
            )

    def validate_search_keywords(
            self,
            search_keywords: str
    ) -> None:
        stripped = search_keywords.strip()
        if not stripped:
            raise DocumentContextProviderError(
                "search_keywords cannot be empty or whitespace-only when provided.",
                status_code=400,
            )
        if len(stripped) > self._settings.max_question_chars:
            raise DocumentContextProviderError(
                f"search_keywords exceeds the maximum allowed length "
                f"of {self._settings.max_question_chars:,} characters.",
                status_code=400,
            )

    def validate_rerank_request_flags(
            self,
            *,
            use_rerank: bool,
            rerank_final_fragments: int | None,
            max_fragments: int,
    ) -> None:
        if rerank_final_fragments is not None:
            if not use_rerank:
                raise DocumentContextProviderError(
                    "rerank_final_fragments may only be set when use_rerank is true.",
                    status_code=400,
                )
            if rerank_final_fragments < 1:
                raise DocumentContextProviderError(
                    "rerank_final_fragments must be at least one when set.",
                    status_code=400,
                )
            if rerank_final_fragments > max_fragments:
                raise DocumentContextProviderError(
                    "rerank_final_fragments must not exceed max_fragments.",
                    status_code=400,
                )

    def validate_max_fragments(
            self,
            max_fragments: int
    ) -> None:
        cap = self._settings.max_fragments_cap
        if max_fragments < 1 or max_fragments > cap:
            raise DocumentContextProviderError(
                f"max_fragments must be between 1 and {cap}.",
                status_code=400
            )

    def validate_document_ids(
            self,
            document_ids: list[int]
    ) -> None:
        if not document_ids:
            raise DocumentContextProviderError(
                "At least one document identifier must be provided.",
                status_code=400
            )
        max_n = self._settings.max_document_ids_per_request
        if len(document_ids) > max_n:
            raise DocumentContextProviderError(
                f"The number of document identifiers cannot exceed {max_n}.",
                status_code=400
            )
        invalid_ids = [doc_id for doc_id in document_ids if doc_id <= 0]
        if invalid_ids:
            raise DocumentContextProviderError(
                "Each document identifier must be a positive integer.",
                status_code=400
            )

    def apply_response_char_limits(
            self,
            fragments: list[FragmentResponse]
    ) -> list[FragmentResponse]:
        if not fragments:
            return []

        max_per = self._settings.max_chars_per_fragment
        max_total = self._settings.max_total_chars
        truncate_each = self._settings.truncate_oversized_fragments

        result: list[FragmentResponse] = []
        total_used = 0

        for fragment in fragments:
            content = fragment.content

            if truncate_each and len(content) > max_per:
                content = content[:max_per]

            remaining = max_total - total_used
            if remaining <= 0:
                break

            need = len(content)
            if need <= remaining:
                result.append(
                    fragment
                    if need == len(fragment.content)
                    else fragment.model_copy(update={"content": content})
                )
                total_used += need
            else:
                result.append(fragment.model_copy(update={"content": content[:remaining]}))
                break

        return result