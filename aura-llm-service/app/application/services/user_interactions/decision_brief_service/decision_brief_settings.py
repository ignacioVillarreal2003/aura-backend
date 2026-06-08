from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionBriefSettings:
    max_title_chars: int = 100
    max_narrative_chars: int = 4_000
    max_option_title_chars: int = 300
    max_option_text_chars: int = 2_000
    max_options: int = 50
