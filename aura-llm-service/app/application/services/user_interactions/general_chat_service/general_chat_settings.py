from dataclasses import dataclass


@dataclass(frozen=True)
class GeneralChatSettings:
    max_response_chars: int = 10_000
