from langchain_text_splitters import CharacterTextSplitter

from app.application.processors.text_splitters.exceptions.text_splitter_exception import TextSplitterException
from app.application.processors.text_splitters.interfaces.text_splitter_adapter_interface import (
    TextSplitterAdapterInterface
)


class CharTiktokenTextSplitterAdapter(TextSplitterAdapterInterface):
    def split_text(
            self,
            text: str,
            size: int,
            overlap: int
    ) -> list[str]:
        try:
            splitter = CharacterTextSplitter.from_tiktoken_encoder(
                encoding_name="cl100k_base",
                chunk_size=size,
                chunk_overlap=overlap,
                separator="\n"
            )
            return splitter.split_text(text)
        except Exception as e:
            raise TextSplitterException(f"Error al generar splits de texto con CharTiktokenTextSplitterAdapter: {str(e)}")
