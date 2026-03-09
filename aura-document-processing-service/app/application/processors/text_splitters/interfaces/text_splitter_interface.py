from abc import ABC, abstractmethod


class TextSplitterInterface(ABC):
    @abstractmethod
    def split_text(
            self,
            text: str
    ) -> list[str]:
        pass
