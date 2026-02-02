import re

from app.application.processors.text_cleaners.interfaces.text_cleaner_adapter_interface import (
    TextCleanerAdapterInterface
)


class FullTextCleanerAdapter(TextCleanerAdapterInterface):
    def clean_text(
            self,
            text: str
    ) -> str:
        if not text:
            return ""

        text = re.sub(r"[\t\r]+", " ", text)
        text = re.sub(r"[^\wáéíóúüñÁÉÍÓÚÜÑ.,;:!?()\"'«»\-\/ \n]+", " ", text)
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)
        text = re.sub(r"[ ]{2,}", " ", text)

        lines = text.split("\n")
        new_lines = []
        buffer = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if len(line.split()) < 5:
                buffer += " " + line
            else:
                if buffer:
                    buffer += " " + line
                    new_lines.append(buffer.strip())
                    buffer = ""
                else:
                    new_lines.append(line)
        if buffer:
            new_lines.append(buffer.strip())

        return "\n\n".join(new_lines).strip()
