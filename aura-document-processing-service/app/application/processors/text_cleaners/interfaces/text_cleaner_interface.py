from abc import ABC, abstractmethod

class TextCleanerInterface(ABC):
    @abstractmethod
    def clean_text(self, text: str) -> str:
        pass
