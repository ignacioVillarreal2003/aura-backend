from enum import Enum


class SummarizationStrategy(str, Enum):
    DIRECT = "direct"
    MAP_REDUCE = "map_reduce"