from types import SimpleNamespace

from app.application.services.fragment.fragment_query_service.fragment_query_service import FragmentQueryService
from app.configuration.metrics import (
    retrieval_lane_fragments_total,
    retrieval_top_rerank_score,
)


def _f(fragment_id):
    return SimpleNamespace(id=fragment_id)


class TestLaneMembership:
    def test_splits_bm25_raw_and_contextual(self):
        lanes = FragmentQueryService._build_lane_membership(
            semantic_ranked_lists=[[_f(1), _f(2)]],
            contextual_ranked_lists=[[_f(2), _f(3)]],
            bm25_ranked_lists=[[_f(4)], [_f(5)]],
            bm25_query_count=1,
        )
        assert lanes["vector_raw"] == {1, 2}
        assert lanes["vector_contextual"] == {2, 3}
        assert lanes["bm25_raw"] == {4}
        assert lanes["bm25_contextual"] == {5}

    def test_no_bm25_lists_yields_empty_bm25_lanes(self):
        lanes = FragmentQueryService._build_lane_membership(
            semantic_ranked_lists=[[_f(1)]],
            contextual_ranked_lists=[],
            bm25_ranked_lists=[],
            bm25_query_count=0,
        )
        assert lanes["bm25_raw"] == set()
        assert lanes["bm25_contextual"] == set()


def _lane_value(lane: str) -> float:
    return retrieval_lane_fragments_total.labels(lane=lane)._value.get()


class TestRecordLaneContribution:
    def test_counts_each_lane_a_fragment_appears_in(self):
        before_raw = _lane_value("vector_raw")
        before_ctx = _lane_value("vector_contextual")
        lane_ids = {"vector_raw": {1, 2}, "vector_contextual": {2}, "bm25_raw": set(), "bm25_contextual": set()}

        FragmentQueryService._record_lane_contribution([_f(1), _f(2)], lane_ids)

        assert _lane_value("vector_raw") == before_raw + 2
        assert _lane_value("vector_contextual") == before_ctx + 1


class TestRecordTopRerankScore:
    def test_observes_max_score(self):
        before = retrieval_top_rerank_score._sum.get()
        FragmentQueryService._record_top_rerank_score([(0, 0.4), (1, 0.92), (2, 0.1)])
        assert retrieval_top_rerank_score._sum.get() == before + 0.92

    def test_empty_scores_is_noop(self):
        before = retrieval_top_rerank_score._sum.get()
        FragmentQueryService._record_top_rerank_score([])
        assert retrieval_top_rerank_score._sum.get() == before
