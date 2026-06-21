import logging
import re
import unicodedata

from app.application.processors.text_cleaners.exceptions.text_cleaner_exception import TextCleanerExecutionException
from app.application.processors.text_cleaners.interfaces.text_cleaner_interface import TextCleanerInterface
from app.application.processors.text_cleaners.text_cleaner_settings import TextCleanerSettings

logger = logging.getLogger(__name__)

_SPANISH_STOP_WORDS: frozenset[str] = frozenset({
    "de", "la", "las", "los", "el", "él", "un", "una", "y", "o", "a", "en",
    "con", "por", "que", "del", "al", "se", "le", "su", "sus", "si", "sí",
    "no", "ni", "ya", "es", "ha", "lo", "me", "te", "nos", "les",
    "eso", "aun", "aún", "mas", "más", "muy", "bien", "son", "fue", "ser", "hay",
    "ver", "dar", "han", "era", "iba", "sin", "tan", "tal", "cual",
    "ahi", "ahí",
})

_HYPHEN_LINEBREAK_RE = re.compile(
    r'([a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+)-[ \t]*\n[ \t]*([a-záéíóúüñ])',
    re.UNICODE,
)

_NOISE_LINE_PATTERN = re.compile(r"^[\-=*#~_\s$%!@^&|+]{3,}$")

_SECTION_LABEL_RE = re.compile(r"^[\dA-ZÁÉÍÓÚÜÑ]+(?:[.\-][\dA-ZÁÉÍÓÚÜÑ]*)*\.?$")

_MARKDOWN_BOLD_ITALIC = re.compile(r"\*{1,3}([^\n]+?)\*{1,3}")
_MARKDOWN_CODE_INLINE = re.compile(r"`([^`\n]+)`")
_MARKDOWN_CODE_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MARKDOWN_BLOCKQUOTE = re.compile(r"^>\s?", re.MULTILINE)

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")

_MULTI_SPACE_PATTERN = re.compile(r"[ ]{2,}")
_MULTI_NEWLINE_PATTERN = re.compile(r"\n{3,}")

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F9FF"
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE,
)


class SimpleTextCleaner(TextCleanerInterface):
    def __init__(
            self,
            text_cleaner_settings: TextCleanerSettings
    ) -> None:
        self._settings = text_cleaner_settings
        logger.info("The simple text cleaner was initialized successfully.")

    def clean_text(
            self,
            text: str
    ) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""

        if len(text) > self._settings.max_text_length:
            raise TextCleanerExecutionException("The text exceeds the maximum allowed length.")

        original_length = len(text)

        try:
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            text = text.replace("\t", " ")

            text = unicodedata.normalize("NFKC", text)

            text = _CONTROL_CHAR_RE.sub("", text)

            text = _EMOJI_PATTERN.sub("", text)
            text = self._remove_markdown(text)
            text = _URL_PATTERN.sub(" ", text)

            text = self._remove_noise_lines(text)

            text = _HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)
            text = self._join_fragmented_lines(text)

            text = self._normalize_whitespace(text)

            result = text.strip()

            logger.debug(
                "The text was cleaned successfully.",
                extra={
                    "input_length": original_length,
                    "output_length": len(result),
                },
            )
            return result

        except TextCleanerExecutionException:
            raise
        except Exception as e:
            logger.exception("Failed to clean the text.")
            raise TextCleanerExecutionException("Failed to clean the text.") from e

    @staticmethod
    def _remove_markdown(text: str) -> str:
        text = _MARKDOWN_IMAGE.sub("", text)
        text = _MARKDOWN_CODE_BLOCK.sub(r"\1", text)
        text = _MARKDOWN_LINK.sub(r"\1", text)
        text = _MARKDOWN_CODE_INLINE.sub(r"\1", text)
        text = _MARKDOWN_BOLD_ITALIC.sub(r"\1", text)
        text = _MARKDOWN_HEADING.sub("", text)
        text = _MARKDOWN_BLOCKQUOTE.sub("", text)
        return text

    @staticmethod
    def _remove_noise_lines(text: str) -> str:
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
                if next_line and not _NOISE_LINE_PATTERN.match(next_line):
                    cleaned.append(f"{line} {next_line}")
                    i += 2
                    continue

            cleaned.append(line)
            i += 1

        return "\n".join(cleaned)

    @staticmethod
    def _join_fragmented_lines(text: str) -> str:
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
            is_numeric_fragment = (
                len(words) == 1
                and line.rstrip(".:,;)").isdigit()
            )

            if output:
                j = len(output) - 1
                while j >= 0 and output[j] == "":
                    j -= 1

                if j >= 0:
                    empty_count = (len(output) - 1) - j
                    prev = output[j]
                    prev_ends_sentence = prev[-1] in ".!?:;"
                    prev_words = prev.split()
                    prev_is_section_label = (
                        len(prev_words) == 1
                        and bool(_SECTION_LABEL_RE.match(prev_words[0]))
                    )
                    prev_is_short_nonfinal = (
                        len(prev_words) <= 2
                        and (not prev_ends_sentence or prev_is_section_label)
                    )

                    should_merge = (
                        empty_count <= 1 and (
                            (starts_lowercase and (is_short_fragment or not prev_ends_sentence))
                            or (is_numeric_fragment and empty_count == 0)
                            or (prev_is_short_nonfinal and is_short_fragment and empty_count == 0)
                            or (prev_is_section_label and empty_count == 0)
                        )
                    )

                    if should_merge:
                        first_word = words[0] if words else ""
                        join_without_space = (
                            not prev_ends_sentence
                            and prev[-1].isalpha()
                            and 1 <= len(first_word) <= 5
                            and first_word.isalpha()
                            and first_word.lower() not in _SPANISH_STOP_WORDS
                        )
                        if join_without_space:
                            output[j] += line
                        else:
                            output[j] += " " + line
                        del output[j + 1:]
                        continue

            output.append(line)

        return "\n".join(output)

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)
        text = _MULTI_SPACE_PATTERN.sub(" ", text)
        text = _MULTI_NEWLINE_PATTERN.sub("\n\n", text)
        return text
