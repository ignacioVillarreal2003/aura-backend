import logging
from dataclasses import dataclass

from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.infrastructure.llm.ollama_llm.ollama_llm_facade_settings import OllamaLLMFacadeSettings

logger = logging.getLogger(__name__)


class InsufficientContextWindowError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContextBudget:
    num_ctx: int
    context_tokens: int
    prompt_overhead_tokens: int
    output_reserve_tokens: int

    @property
    def required_tokens(self) -> int:
        return self.context_tokens + self.prompt_overhead_tokens + self.output_reserve_tokens

    @property
    def fits(self) -> bool:
        return self.num_ctx >= self.required_tokens

    @property
    def headroom_tokens(self) -> int:
        return self.num_ctx - self.required_tokens

    def as_log_extra(self) -> dict:
        return {
            "num_ctx": self.num_ctx,
            "required_tokens": self.required_tokens,
            "context_tokens": self.context_tokens,
            "prompt_overhead_tokens": self.prompt_overhead_tokens,
            "output_reserve_tokens": self.output_reserve_tokens,
            "headroom_tokens": self.headroom_tokens,
        }


def compute_context_budget(
        facade_settings: OllamaLLMFacadeSettings,
        generation_settings: GenerationSettings,
) -> ContextBudget:
    return ContextBudget(
        num_ctx=facade_settings.num_ctx,
        context_tokens=generation_settings.max_context_tokens,
        prompt_overhead_tokens=facade_settings.prompt_overhead_tokens,
        output_reserve_tokens=facade_settings.output_reserve(),
    )


def validate_context_budget(
        facade_settings: OllamaLLMFacadeSettings,
        generation_settings: GenerationSettings,
) -> ContextBudget:
    budget = compute_context_budget(facade_settings, generation_settings)

    if budget.fits:
        logger.info("Context window budget validated.", extra=budget.as_log_extra())
        return budget

    message = (
        "num_ctx is smaller than the required prompt budget; prompts may be "
        "silently truncated by Ollama. Increase OLLAMA_LLM_FACADE_NUM_CTX or "
        "lower GENERATION_MAX_CONTEXT_TOKENS / num_predict."
    )
    if facade_settings.fail_on_insufficient_context:
        logger.critical(message, extra=budget.as_log_extra())
        raise InsufficientContextWindowError(message)
    logger.warning(message, extra=budget.as_log_extra())
    return budget
