import re
from app.application.processors.text_cleaners.interfaces.text_cleaner_interface import TextCleanerInterface


class BasicTextCleaner(TextCleanerInterface):
    def clean_text(self, text: str) -> str:
        if not text:
            return ""

        text = re.sub(r"[\t\n\r]+", " ", text)
        text = re.sub(r"[^\wáéíóúüñÁÉÍÓÚÜÑ.,;:!?()\"'«»\-\/ ]+", " ", text)
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)
        text = re.sub(r"\s{2,}", " ", text)

        return text.strip()
