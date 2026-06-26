from app.infrastructure.http.document_context_provider.dtos.fragment_list_response import FragmentListResponse
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
from app.infrastructure.http.document_context_provider.dtos.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)
from app.infrastructure.http.document_context_provider.exceptions.document_context_provider_exception import (
    DocumentContextProviderInvalidResponseException,
)


def calculate_question_response_max_fragments(
        request_body: QuestionContextFragmentsRequest,
) -> int:
    if request_body.rerank.enabled and request_body.rerank.max_fragments is not None:
        return request_body.rerank.max_fragments
    return (
            sum(q.max_fragments for q in request_body.semantic_queries)
            + sum(q.max_fragments for q in request_body.bm25_queries)
    )


def apply_fragment_count_limit(
        fragments: list[FragmentResponse],
        max_fragments: int,
) -> list[FragmentResponse]:
    return fragments[:max_fragments]


def parse_and_apply_limits(
        raw_data: dict,
        max_fragments: int,
) -> FragmentListResponse:
    try:
        response = FragmentListResponse.model_validate(raw_data)
    except Exception as e:
        raise DocumentContextProviderInvalidResponseException(
            "The context service returned an invalid response format."
        ) from e

    limited = apply_fragment_count_limit(
        fragments=response.fragments,
        max_fragments=max_fragments,
    )
    return FragmentListResponse(fragments=limited, groups=response.groups)
