from unittest.mock import MagicMock

import pytest

from app.application.processors.rerankers.instances.cross_encoder_reranker import CrossEncoderReranker
from app.application.processors.rerankers.reranker_settings import RerankerSettings


class _FakeModel:
    def __init__(self, scores):
        self._scores = scores

    def predict(self, pairs, batch_size=16, show_progress_bar=False, **kwargs):
        return self._scores


def _reranker(monkeypatch, scores, *, min_score, fallback):
    settings = RerankerSettings(min_score=min_score, min_score_fallback_to_topk=fallback)
    reranker = CrossEncoderReranker(settings)

    async def _fake_load(cls, _settings):
        return _FakeModel(scores)

    monkeypatch.setattr(CrossEncoderReranker, "_get_or_load_model", classmethod(_fake_load))
    return reranker


class TestRerankFallback:
    async def test_keeps_only_above_threshold_when_some_pass(self, monkeypatch):
        r = _reranker(monkeypatch, [0.9, 0.1, 0.5], min_score=0.35, fallback=True)
        scored = await r.rerank_with_scores("q", ["a", "b", "c"], top_n=3)
        kept = {idx for idx, _ in scored}
        assert kept == {0, 2}

    async def test_all_below_with_fallback_returns_topk(self, monkeypatch):
        r = _reranker(monkeypatch, [0.10, 0.20, 0.05], min_score=0.35, fallback=True)
        scored = await r.rerank_with_scores("q", ["a", "b", "c"], top_n=3)
        assert len(scored) == 3

    async def test_all_below_without_fallback_returns_empty(self, monkeypatch):
        r = _reranker(monkeypatch, [0.10, 0.20, 0.05], min_score=0.35, fallback=False)
        scored = await r.rerank_with_scores("q", ["a", "b", "c"], top_n=3)
        assert scored == []

    async def test_default_fallback_is_enabled(self):
        assert RerankerSettings().min_score_fallback_to_topk is True
