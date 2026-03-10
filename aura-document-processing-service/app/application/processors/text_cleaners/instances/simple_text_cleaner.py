import re

from app.application.processors.text_cleaners.interfaces.text_cleaner_interface import TextCleanerInterface


class SimpleTextCleaner(TextCleanerInterface):
    _NOISE_LINE_PATTERN = re.compile(r"^[\-=*#~_\s$%!@^&|+]{3,}$")

    _MARKDOWN_BOLD_ITALIC = re.compile(r"\*{1,3}(.+?)\*{1,3}")
    _MARKDOWN_CODE_INLINE = re.compile(r"`(.+?)`")
    _MARKDOWN_LINK = re.compile(r"\[(.+?)\]\(.*?\)")

    _URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")

    _EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F9FF"
        "\U00002700-\U000027BF"
        "]+",
        flags=re.UNICODE
    )

    def clean_text(
            self,
            text: str
    ) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""

        text = text.replace("\r\n", "\n").replace("\r", "\n")

        text = re.sub(r"(?<![.\:\-\n])\n(?![0-9\-\*\•\n])", " ", text)

        text = text.replace("\t", " ")

        text = self._EMOJI_PATTERN.sub("", text)

        text = self._MARKDOWN_BOLD_ITALIC.sub(r"\1", text)
        text = self._MARKDOWN_CODE_INLINE.sub(r"\1", text)
        text = self._MARKDOWN_LINK.sub(r"\1", text)

        text = self._URL_PATTERN.sub("", text)

        lines = text.split("\n")
        cleaned_lines = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if self._NOISE_LINE_PATTERN.match(line):
                i += 1
                continue

            if line in ("-", "*", "•") and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line:
                    cleaned_lines.append(f"{line} {next_line}")
                    i += 2
                    continue

            cleaned_lines.append(line)
            i += 1

        text = "\n".join(cleaned_lines)

        text = re.sub(r"[ ]{2,}", " ", text)

        text = re.sub(r"\n{2,}", "\n", text)

        return text.strip()
