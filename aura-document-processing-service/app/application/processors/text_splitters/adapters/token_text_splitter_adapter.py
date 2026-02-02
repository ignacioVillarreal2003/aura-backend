from langchain_text_splitters import TokenTextSplitter

from app.application.processors.text_splitters.exceptions.text_splitter_exception import TextSplitterError
from app.application.processors.text_splitters.interfaces.text_splitter_adapter_interface import (
    TextSplitterAdapterInterface
)


class TokenTextSplitterAdapter(TextSplitterAdapterInterface):
    def split_text(
            self,
            text: str,
            size: int,
            overlap: int
    ) -> list[str]:
        try:
            splitter = TokenTextSplitter(
                chunk_size=size,
                chunk_overlap=overlap,
                encoding_name="cl100k_base"
            )
            return splitter.split_text(text)
        except Exception as e:
            raise TextSplitterError(f"Error al generar splits de texto con TokenTextSplitterAdapter: {str(e)}")
