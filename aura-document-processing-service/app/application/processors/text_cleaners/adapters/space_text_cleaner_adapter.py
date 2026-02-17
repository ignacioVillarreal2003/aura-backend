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

        text = re.sub(r"\n\s*\n", " ", text)
        text = re.sub(r"\n", " ", text)
        text = re.sub(r"[\t\r]", " ", text)
        text = re.sub(r"\s{2,}", " ", text)

        return text.strip()
