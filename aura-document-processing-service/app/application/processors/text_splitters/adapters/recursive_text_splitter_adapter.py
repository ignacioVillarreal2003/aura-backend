from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.application.exceptions.api_exceptions import TextSplitterError
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class RecursiveTextSplitterAdapter(TextSplitterInterface):
    def split_text(self,
                   text: str,
                   size: int,
                   overlap: int) -> list[str]:
        try:
            splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                model_name="gpt-4",
                chunk_size=size,
                chunk_overlap=overlap
            )
            return splitter.split_text(text)
        except Exception as e:
            raise TextSplitterError(f"Error al generar splits de texto con RecursiveTextSplitterAdapter: {str(e)}")
