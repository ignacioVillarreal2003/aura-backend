import logging
import re

from app.application.processors.text_cleaners.exceptions.text_cleaner_exception import TextCleanerExecutionException
from app.application.processors.text_cleaners.interfaces.text_cleaner_interface import TextCleanerInterface
from app.application.processors.text_cleaners.text_cleaner_settings import TextCleanerSettings

logger = logging.getLogger(__name__)

_NOISE_LINE_PATTERN = re.compile(r"^[\-=*#~_\s$%!@^&|+]{3,}$")

_MARKDOWN_BOLD_ITALIC = re.compile(r"\*{1,3}(.+?)\*{1,3}")
_MARKDOWN_CODE_INLINE = re.compile(r"`(.+?)`")
_MARKDOWN_LINK = re.compile(r"\[(.+?)\]\(.*?\)")

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")

_MULTI_SPACE_PATTERN = re.compile(r"[ ]{2,}")
_MULTI_NEWLINE_PATTERN = re.compile(r"\n{2,}")
_BLANK_LINE_PATTERN = re.compile(r"\n[ \t]+\n")

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F9FF"
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE
)


class SimpleTextCleaner(TextCleanerInterface):
    def __init__(
            self,
            text_cleaner_settings: TextCleanerSettings
    ) -> None:
        self._settings = text_cleaner_settings

        logger.info(
            "The simple text cleaner was initialized successfully.",
            extra={
                "remove_urls": self._settings.simple_remove_urls,
                "remove_emojis": self._settings.simple_remove_emojis,
                "remove_markdown": self._settings.simple_remove_markdown,
                "normalize_whitespace": self._settings.simple_normalize_whitespace,
                "remove_noise_lines": self._settings.simple_remove_noise_lines
            }
        )

    def clean_text(
            self,
            text: str
    ) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""

        if len(text) > self._settings.max_text_length:
            raise TextCleanerExecutionException("The text exceeds the maximum allowed length.")

        try:
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            text = text.replace("\t", " ")

            text = self._remove_emojis(text)
            text = self._remove_markdown(text)
            text = self._remove_urls(text)
            text = self._remove_noise_lines(text)
            text = self._join_fragmented_lines(text)
            text = self._remove_normalize_whitespace(text)

            result = text.strip()

            logger.debug(
                "The text was cleaned successfully.",
                extra={
                    "input_length": len(text),
                    "output_length": len(result)
                }
            )

            return result

        except TextCleanerExecutionException:
            raise
        except Exception as e:
            logger.exception("Failed to clean the text.")
            raise TextCleanerExecutionException("Failed to clean the text.") from e

    def _remove_emojis(
            self,
            text: str
    ) -> str:
        if self._settings.simple_remove_emojis:
            text = _EMOJI_PATTERN.sub("", text)
        return text

    def _remove_markdown(
            self,
            text: str
    ) -> str:
        if self._settings.simple_remove_markdown:
            text = _MARKDOWN_BOLD_ITALIC.sub(r"\1", text)
            text = _MARKDOWN_CODE_INLINE.sub(r"\1", text)
            text = _MARKDOWN_LINK.sub(r"\1", text)
        return text

    def _remove_urls(
            self,
            text: str
    ) -> str:
        if self._settings.simple_remove_urls:
            text = _URL_PATTERN.sub("", text)
        return text

    def _remove_noise_lines(
            self,
            text: str
    ) -> str:
        if self._settings.simple_remove_noise_lines:
            lines = text.split("\n")
            cleaned: list[str] = []
            i = 0

            while i < len(lines):
                line = lines[i].strip()

                if _NOISE_LINE_PATTERN.match(line):
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
        return text

    def _join_fragmented_lines(
            self,
            text: str
    ) -> str:
        if self._settings.simple_join_fragmented_lines:
            lines = text.split("\n")
            output: list[str] = []

            for raw in lines:
                line = raw.strip()

                if not line:
                    output.append("")
                    continue

                words = line.split()
                is_short_fragment = len(words) <= 2
                starts_lowercase = line[0].islower()

                if output:
                    j = len(output) - 1
                    while j >= 0 and output[j] == "":
                        j -= 1

                    if j >= 0:
                        empty_count = (len(output) - 1) - j
                        prev_ends_sentence = output[j][-1] in ".!?:;"

                        should_merge = (
                                starts_lowercase and empty_count <= 1
                                and (is_short_fragment or not prev_ends_sentence)
                        )

                        if should_merge:
                            output[j] += " " + line
                            del output[j + 1:]
                            continue

                output.append(line)

            return "\n".join(output)
        return text

    def _remove_normalize_whitespace(
            self,
            text: str
    ) -> str:
        if self._settings.simple_normalize_whitespace:
            lines = [line.rstrip() for line in text.split("\n")]
            text = "\n".join(lines)
            text = _MULTI_SPACE_PATTERN.sub(" ", text)
            text = _MULTI_NEWLINE_PATTERN.sub("\n\n", text)
        return text
