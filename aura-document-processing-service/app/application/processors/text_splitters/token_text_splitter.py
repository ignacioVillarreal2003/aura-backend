from langchain_text_splitters import TokenTextSplitter

from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class TokenTextSplitter(TextSplitterInterface):
    def split_text(self,
                   text: str,
                   size: int,
                   overlap: int) -> list[str]:
        splitter = TokenTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap
        )
        return splitter.split_text(text)
