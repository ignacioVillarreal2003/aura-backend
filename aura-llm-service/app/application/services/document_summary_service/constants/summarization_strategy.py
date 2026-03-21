from enum import Enum


class SummarizationStrategy(str, Enum):
    direct = "direct"
    map_reduce = "map_reduce"
