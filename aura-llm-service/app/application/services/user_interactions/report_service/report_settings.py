from dataclasses import dataclass


@dataclass(frozen=True)
class ReportSettings:
    max_content_chars: int = 50_000
