from enum import Enum


class DocumentActionType(str, Enum):
    summarize = "summarize"
    essay = "essay"
    key_points = "key_points"
    compare = "compare"
    analyze = "analyze"
    explain = "explain"
    report = "report"
