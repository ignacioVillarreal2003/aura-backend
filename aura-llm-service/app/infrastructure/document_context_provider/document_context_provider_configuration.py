from dataclasses import dataclass


@dataclass(frozen=True)
class ContextProviderConfiguration:
    default_fragments_count: int = 3
    min_fragments_count: int = 1
    max_fragments_count: int = 6

    max_fragment_chars: int = 10000
    truncate_oversized_fragments: bool = False

    max_total_fragments_in_response: int = 100
    max_response_size_chars: int = 500000

    def __post_init__(self):
        self._validate()

    def _validate(self) -> None:
        if not (1 <= self.min_fragments_count <= self.max_fragments_count):
            raise ValueError(
                f"Invalid fragments count range: min={self.min_fragments_count}, "
                f"max={self.max_fragments_count}"
            )

        if not (self.min_fragments_count <= self.default_fragments_count <= self.max_fragments_count):
            raise ValueError(
                f"default_fragments_count ({self.default_fragments_count}) must be "
                f"between min ({self.min_fragments_count}) and max ({self.max_fragments_count})"
            )

        if self.max_fragment_chars <= 0:
            raise ValueError("max_fragment_chars must be positive")

        if self.max_total_fragments_in_response <= 0:
            raise ValueError("max_total_fragments_in_response must be positive")

        if self.max_response_size_chars <= 0:
            raise ValueError("max_response_size_chars must be positive")
