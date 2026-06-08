from enum import Enum


class ProcessingStrategy(str, Enum):
    direct = "direct"
    map_reduce = "map_reduce"
