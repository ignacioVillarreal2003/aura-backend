from langchain_text_splitters import SpacyTextSplitter

from app.application.exceptions.api_exceptions import TextSplitterError
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class SpacyTextSplitterAdapter(TextSplitterInterface):
    def split_text(self,
                   text: str,
                   size: int,
                   overlap: int) -> list[str]:
        try:
            splitter = SpacyTextSplitter(
                chunk_size=size,
                chunk_overlap=overlap,
                pipeline="es_core_news_sm"
            )
            return splitter.split_text(text)
        except Exception as e:
            raise TextSplitterError(f"Error al generar splits de texto con SpacyTextSplitterAdapter: {str(e)}")
