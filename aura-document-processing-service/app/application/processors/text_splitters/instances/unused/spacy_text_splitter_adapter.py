from langchain_text_splitters import SpacyTextSplitter

from app.application.processors.text_splitters.exceptions.text_splitter_exception import TextSplitterExecutionException
from app.application.processors.text_splitters.interfaces.text_splitter_interface import (
    TextSplitterAdapterInterface
)


class SpacyTextSplitterAdapter(TextSplitterAdapterInterface):
    def split_text(
            self,
            text: str,
            size: int,
            overlap: int
    ) -> list[str]:
        try:
            splitter = SpacyTextSplitter(
                chunk_size=size,
                chunk_overlap=overlap,
                pipeline="es_core_news_sm"
            )
            return splitter.split_text(text)
        except Exception as e:
            raise TextSplitterExecutionException("SpacyTextSplitterAdapter", e)
