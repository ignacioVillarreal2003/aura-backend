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

        # Remove carriage returns and tabs
        text = re.sub(r"[\t\r]", " ", text)

        # Normalize multiple blank lines to a single paragraph separator
        # This preserves the \n\n boundary that RecursiveCharacterTextSplitter uses
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Collapse multiple spaces within a line (but not newlines)
        text = re.sub(r"[ ]{2,}", " ", text)

        # Clean trailing/leading spaces on each line
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        return text.strip()
