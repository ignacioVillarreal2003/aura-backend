from langchain_text_splitters import CharacterTextSplitter
from transformers import GPT2TokenizerFast

from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class HuggingfaceTextSplitter(TextSplitterInterface):
    def split_text(self,
                   text: str,
                   size: int,
                   overlap: int) -> list[str]:
        tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
        splitter = CharacterTextSplitter.from_huggingface_tokenizer(
            tokenizer,
            chunk_size=size,
            chunk_overlap=overlap,
            separator="\n"
        )
        return splitter.split_text(text)
