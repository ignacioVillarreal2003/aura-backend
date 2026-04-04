import logging
import re

from app.application.processors.text_cleaners.exceptions.text_cleaner_exception import (
    TextCleanerInitializationException,
    TextCleanerExecutionException
)
from app.application.processors.text_cleaners.interfaces.text_cleaner_interface import TextCleanerInterface
from app.application.processors.text_cleaners.text_cleaner_settings import TextCleanerSettings

logger = logging.getLogger(__name__)


class SimpleTextCleaner(TextCleanerInterface):
    _NOISE_LINE_PATTERN = re.compile(r"^[\-=*#~_\s$%!@^&|+]{3,}$")

    _MARKDOWN_BOLD_ITALIC = re.compile(r"\*{1,3}(.+?)\*{1,3}")
    _MARKDOWN_CODE_INLINE = re.compile(r"`(.+?)`")
    _MARKDOWN_LINK = re.compile(r"\[(.+?)\]\(.*?\)")

    _URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")

    _SOFT_NEWLINE_PATTERN = re.compile(r"(?<![.\:\-\n])\n(?![0-9\-\*\•\n])")
    _MULTI_SPACE_PATTERN = re.compile(r"[ ]{2,}")
    _MULTI_NEWLINE_PATTERN = re.compile(r"\n{2,}")

    _EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F9FF"
        "\U00002700-\U000027BF"
        "]+",
        flags=re.UNICODE
    )

    def __init__(self, text_cleaner_settings: TextCleanerSettings) -> None:
        self._settings = text_cleaner_settings

        try:
            logger.info(
                "SimpleTextCleaner initialized successfully",
                extra={
                    "remove_urls": self._settings.simple_remove_urls,
                    "remove_emojis": self._settings.simple_remove_emojis,
                    "remove_markdown": self._settings.simple_remove_markdown,
                    "normalize_whitespace": self._settings.simple_normalize_whitespace,
                    "remove_noise_lines": self._settings.simple_remove_noise_lines
                }
            )
        except Exception as e:
            logger.exception("Failed to initialize SimpleTextCleaner")
            raise TextCleanerInitializationException(
                f"SimpleTextCleaner initialization failed: {e}"
            ) from e

    def clean_text(self, text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""

        if len(text) > self._settings.max_text_length:
            raise TextCleanerExecutionException(
                f"Text length ({len(text)}) exceeds maximum allowed "
                f"({self._settings.max_text_length})"
            )

        try:
            text = text.replace("\r\n", "\n").replace("\r", "\n")

            text = self._SOFT_NEWLINE_PATTERN.sub(" ", text)

            text = text.replace("\t", " ")

            if self._settings.simple_remove_emojis:
                text = self._EMOJI_PATTERN.sub("", text)

            if self._settings.simple_remove_markdown:
                text = self._MARKDOWN_BOLD_ITALIC.sub(r"\1", text)
                text = self._MARKDOWN_CODE_INLINE.sub(r"\1", text)
                text = self._MARKDOWN_LINK.sub(r"\1", text)

            if self._settings.simple_remove_urls:
                text = self._URL_PATTERN.sub("", text)

            if self._settings.simple_remove_noise_lines:
                text = self._clean_noise_lines(text)

            if self._settings.simple_normalize_whitespace:
                text = self._MULTI_SPACE_PATTERN.sub(" ", text)
                text = self._MULTI_NEWLINE_PATTERN.sub("\n", text)

            result = text.strip()

            logger.debug(
                "Text cleaned successfully",
                extra={"input_length": len(text), "output_length": len(result)}
            )

            return result

        except TextCleanerExecutionException:
            raise
        except Exception as e:
            logger.exception("Failed to clean text")
            raise TextCleanerExecutionException(
                f"SimpleTextCleaner failed to clean text: {e}"
            ) from e

    def _clean_noise_lines(self, text: str) -> str:
        lines = text.split("\n")
        cleaned: list[str] = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if self._NOISE_LINE_PATTERN.match(line):
                i += 1
                continue

            if line in ("-", "*", "•") and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line:
                    cleaned.append(f"{line} {next_line}")
                    i += 2
                    continue

            cleaned.append(line)
            i += 1

        return "\n".join(cleaned)
