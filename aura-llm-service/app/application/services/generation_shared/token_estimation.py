APPROX_CHARS_PER_TOKEN = 4

DEFAULT_MAX_CONTEXT_CHARS = 10_000


def tokens_to_chars(tokens: int) -> int:
    return tokens * APPROX_CHARS_PER_TOKEN


def chars_to_tokens(chars: int) -> int:
    return chars // APPROX_CHARS_PER_TOKEN
