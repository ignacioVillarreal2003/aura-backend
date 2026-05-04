from typing import Optional

from app.infrastructure.http.document_context_provider.dtos.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
    RerankConfig,
    SemanticQuery,
)


def build_legacy_question_retrieval_request(
        question: str,
        question_max_fragments: int,
        use_keywords: Optional[bool],
        keywords: Optional[str],
        keywords_max_fragments: Optional[int],
        use_rerank: Optional[bool],
        rerank_max_fragments: Optional[int],
        chat_id: Optional[int] = None,
) -> QuestionContextFragmentsRequest:
    """Maps the pre-hybrid API shape to ``QuestionContextFragmentsRequest`` (semantic-only + optional rerank)."""
    q = question.strip()
    semantic_queries = [
        SemanticQuery(text=q, max_fragments=question_max_fragments),
    ]
    if use_keywords and keywords and keywords.strip() and keywords_max_fragments:
        semantic_queries.append(
            SemanticQuery(text=keywords.strip(), max_fragments=keywords_max_fragments)
        )

    pool = sum(s.max_fragments for s in semantic_queries)
    rerank = RerankConfig(enabled=False)
    if use_rerank and rerank_max_fragments is not None and pool > 0:
        effective = min(rerank_max_fragments, pool)
        if effective >= 1:
            rerank = RerankConfig(enabled=True, max_fragments=effective)

    return QuestionContextFragmentsRequest(
        chat_id=chat_id,
        semantic_queries=semantic_queries,
        bm25_queries=[],
        rerank=rerank,
    )
