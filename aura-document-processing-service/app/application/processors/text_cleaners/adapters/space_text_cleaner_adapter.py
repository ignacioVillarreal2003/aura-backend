import re

from app.application.processors.text_cleaners.interfaces.text_cleaner_adapter_interface import (
    TextCleanerAdapterInterface
)


class SpaceTextCleanerAdapter(TextCleanerAdapterInterface):
    def clean_text(
            self,
            text: str
    ) -> str:
        if not text:
            return ""

        text = re.sub(r"[\t\r]+", " ", text)
        text = re.sub(r"[ ]{2,}", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)

        return text.strip()
