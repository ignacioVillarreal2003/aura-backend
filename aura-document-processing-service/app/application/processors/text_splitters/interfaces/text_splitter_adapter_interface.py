from abc import ABC, abstractmethod


class TextSplitterAdapterInterface(ABC):
    @abstractmethod
    def split_text(
            self,
            text: str,
            size: int,
            overlap: int
    ) -> list[str]:
        pass
