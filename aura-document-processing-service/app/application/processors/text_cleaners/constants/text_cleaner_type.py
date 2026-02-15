from enum import Enum


class TextCleanerType(str, Enum):
    full = "full"
    no_line_breaks = "no_line_breaks",
    space = "space"
