import re

from app.application.processors.text_cleaners.interfaces.text_cleaner_interface import TextCleanerInterface


class NoLineBreaksTextCleanerAdapter(TextCleanerInterface):
    def clean_text(self,
                   text: str) -> str:
        if not text:
            return ""

        text = re.sub(r"[\t\n\r]+", " ", text)
        text = re.sub(r"[ ]{2,}", " ", text)

        return text.strip()
