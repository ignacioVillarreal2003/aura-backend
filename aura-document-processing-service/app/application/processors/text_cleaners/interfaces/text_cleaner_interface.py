from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.processors.text_cleaners.text_cleaner_settings import TextCleanerSettings


class TextCleanerInterface(ABC):
    @abstractmethod
    def __init__(self, text_cleaner_settings: "TextCleanerSettings") -> None:
        ...

    @abstractmethod
    def clean_text(
            self,
            text: str
    ) -> str:
        pass
