from dataclasses import dataclass


@dataclass(frozen=True)
class ContextProviderConfiguration:
    max_fragment_chars: int = 10000
    truncate_oversized_fragments: bool = False

    max_total_fragments_in_response: int = 100
    max_response_size_chars: int = 500000

    def __post_init__(self):
        self._validate()

    def _validate(self) -> None:
        if self.max_fragment_chars <= 0:
            raise ValueError("max_fragment_chars must be positive")

        if self.max_total_fragments_in_response <= 0:
            raise ValueError("max_total_fragments_in_response must be positive")

        if self.max_response_size_chars <= 0:
            raise ValueError("max_response_size_chars must be positive")
