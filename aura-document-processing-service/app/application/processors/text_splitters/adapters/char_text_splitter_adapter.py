from langchain_text_splitters import CharacterTextSplitter

from app.application.exceptions.api_exceptions import TextSplitterError
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class CharTextSplitterAdapter(TextSplitterInterface):
    def split_text(self,
                   text: str,
                   size: int,
                   overlap: int) -> list[str]:
        try:
            splitter = CharacterTextSplitter(
                chunk_size=size,
                chunk_overlap=overlap,
                separator="\n"
            )
            return splitter.split_text(text)
        except Exception as e:
            raise TextSplitterError(f"Error al generar splits de texto con CharTextSplitterAdapter: {str(e)}")
