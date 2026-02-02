from abc import ABC, abstractmethod


class TextCleanerAdapterInterface(ABC):
    @abstractmethod
    def clean_text(
            self,
            text: str
    ) -> str:
        pass
