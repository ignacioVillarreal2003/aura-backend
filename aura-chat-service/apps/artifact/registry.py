ARTIFACT_TYPES: frozenset[str] = frozenset(
    {
        "MESSAGE",
        "REPORT",
        "CHECKLIST",
        "QUIZ",
        "TIMELINE",
        "LESSONS_LEARNED",
        "DECISION_BRIEF",
        "DOCUMENT_SUMMARY",
        "DOCUMENT_ACTION",
    }
)


def is_known_type(value: str) -> bool:
    return value in ARTIFACT_TYPES
