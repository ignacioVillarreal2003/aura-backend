from abc import ABC, abstractmethod


class TextSplitterInterface(ABC):
    @abstractmethod
    def split_text(
            self,
            text: str
    ) -> list[str]:
        pass

    def get_chunk_params(self) -> tuple[int | None, int | None]:
        """Return the (chunk_size, chunk_overlap) used, for ingestion traceability."""
        return None, None
