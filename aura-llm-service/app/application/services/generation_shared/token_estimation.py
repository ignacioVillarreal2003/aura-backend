APPROX_CHARS_PER_TOKEN = 4

# Single source for the default context-block budget. Every stage that limits the
# assembled context (prompt assembly, retrieval cap, reduction target) defaults
# to this so the budgets stay aligned. The model's num_ctx is the enforced
# ceiling for this budget — see app/configuration/context_budget.py (C1).
DEFAULT_MAX_CONTEXT_CHARS = 10_000


def tokens_to_chars(tokens: int) -> int:
    return tokens * APPROX_CHARS_PER_TOKEN


def chars_to_tokens(chars: int) -> int:
    return chars // APPROX_CHARS_PER_TOKEN
