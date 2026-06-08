from dataclasses import dataclass


@dataclass(frozen=True)
class LessonsLearnedSettings:
    max_title_chars: int = 100
    max_narrative_chars: int = 4_000
    max_observation_chars: int = 2_000
    max_items: int = 300
