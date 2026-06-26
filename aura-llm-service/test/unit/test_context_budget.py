"""Unit tests for context_budget: the ContextBudget arithmetic and
validate_context_budget's warn-vs-raise behaviour driven by
fail_on_insufficient_context. Settings use _env_file=None for determinism."""
import pytest

from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.configuration.context_budget import (
    ContextBudget,
    InsufficientContextWindowError,
    compute_context_budget,
    validate_context_budget,
)
from app.infrastructure.llm.ollama_llm.ollama_llm_facade_settings import OllamaLLMFacadeSettings


def _facade(**overrides) -> OllamaLLMFacadeSettings:
    base = dict(model_name="test-model", base_url="http://ollama.test")
    base.update(overrides)
    return OllamaLLMFacadeSettings(_env_file=None, **base)


def _gen(**overrides) -> GenerationSettings:
    return GenerationSettings(_env_file=None, **overrides)


class TestContextBudgetArithmetic:
    def test_required_headroom_and_fits(self):
        budget = ContextBudget(
            num_ctx=1000, context_tokens=200, prompt_overhead_tokens=100, output_reserve_tokens=300
        )
        assert budget.required_tokens == 600
        assert budget.headroom_tokens == 400
        assert budget.fits is True

    def test_does_not_fit_has_negative_headroom(self):
        budget = ContextBudget(
            num_ctx=500, context_tokens=400, prompt_overhead_tokens=100, output_reserve_tokens=300
        )
        assert budget.fits is False
        assert budget.headroom_tokens == -300


class TestComputeBudget:
    def test_num_predict_takes_precedence_for_output_reserve(self):
        facade = _facade(num_ctx=8192, num_predict=2000, prompt_overhead_tokens=1000)
        budget = compute_context_budget(facade, _gen(max_context_tokens=1000))
        assert budget.output_reserve_tokens == 2000
        assert budget.prompt_overhead_tokens == 1000
        assert budget.context_tokens == 1000
        assert budget.num_ctx == 8192


class TestValidateBudget:
    def test_fitting_budget_returns_without_raising(self):
        budget = validate_context_budget(_facade(num_ctx=16384), _gen(max_context_tokens=256))
        assert budget.fits is True

    def test_insufficient_budget_warns_by_default(self):
        facade = _facade(num_ctx=600, num_predict=None, output_reserve_tokens=500, prompt_overhead_tokens=0)
        budget = validate_context_budget(facade, _gen(max_context_tokens=256))
        assert budget.fits is False  # warned, not raised

    def test_insufficient_budget_raises_when_configured(self):
        facade = _facade(
            num_ctx=600,
            num_predict=None,
            output_reserve_tokens=500,
            prompt_overhead_tokens=0,
            fail_on_insufficient_context=True,
        )
        with pytest.raises(InsufficientContextWindowError):
            validate_context_budget(facade, _gen(max_context_tokens=256))
