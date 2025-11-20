from langchain_text_splitters import CharacterTextSplitter

from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class CharTiktokenTextSplitter(TextSplitterInterface):
    def split_text(self,
                   text: str,
                   size: int,
                   overlap: int) -> list[str]:
        splitter = CharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=size,
            chunk_overlap=overlap,
            separator="\n"
        )
        return splitter.split_text(text)