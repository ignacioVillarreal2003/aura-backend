from enum import Enum


class TextCleanerType(str, Enum):
    FULL = "full"
    NO_LINE_BREAKS = "no_line_breaks",
    SPACE = "space"
