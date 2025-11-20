from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class RecursiveTextSplitter(TextSplitterInterface):
    def split_text(self,
                   text: str,
                   size: int,
                   overlap: int) -> list[str]:
        splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4",
            chunk_size=size,
            chunk_overlap=overlap
        )
        return splitter.split_text(text)
