from dataclasses import dataclass


@dataclass(frozen=True)
class TimelineSettings:
    max_title_chars: int = 100
    max_summary_chars: int = 1_000
    max_event_chars: int = 300
    max_description_chars: int = 2_000
    max_label_chars: int = 100
    max_events: int = 300
