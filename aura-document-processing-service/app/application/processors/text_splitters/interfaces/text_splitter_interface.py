from abc import ABC, abstractmethod


class TextSplitterInterface(ABC):
    @abstractmethod
    def split_text(self,
                   text: str,
                   size: int,
                   overlap: int) -> list[str]:
        pass