from dataclasses import dataclass


@dataclass(frozen=True)
class ChecklistSettings:
    max_title_chars: int = 100
    max_item_text_chars: int = 500
    max_section_chars: int = 200
    max_items: int = 200
