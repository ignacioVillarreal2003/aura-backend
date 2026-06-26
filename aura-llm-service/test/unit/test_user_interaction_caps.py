"""Regression tests: structured user-interaction service settings must never
allow more items than the domain response model accepts. A verbose LLM that
returns more than the domain cap must be truncated at parse time (not raise a
ValidationError that surfaces as a 500). Also covers the checklist defensive
order parsing."""
import json

import pytest
from pydantic import ValidationError

from app.application.services.user_interactions.checklist_service.checklist_service import _parse_llm_output
from app.application.services.user_interactions.checklist_service.checklist_settings import ChecklistSettings
from app.application.services.user_interactions.decision_brief_service.decision_brief_settings import (
    DecisionBriefSettings,
)
from app.application.services.user_interactions.lessons_learned_service.lessons_learned_settings import (
    LessonsLearnedSettings,
)
from app.application.services.user_interactions.quiz_service.quiz_settings import QuizSettings
from app.domain.field_limits import (
    MAX_DECISION_BRIEF_OPTIONS,
    MAX_LESSONS_LEARNED_ITEMS,
    MAX_QUIZ_OPTIONS_PER_QUESTION,
    MAX_QUIZ_QUESTIONS,
)


class TestSettingsCapsWithinDomain:
    def test_quiz_caps_within_domain(self):
        s = QuizSettings(_env_file=None)
        assert s.max_questions <= MAX_QUIZ_QUESTIONS
        assert s.max_options <= MAX_QUIZ_OPTIONS_PER_QUESTION

    def test_lessons_learned_cap_within_domain(self):
        assert LessonsLearnedSettings(_env_file=None).max_items <= MAX_LESSONS_LEARNED_ITEMS

    def test_decision_brief_cap_within_domain(self):
        assert DecisionBriefSettings(_env_file=None).max_options <= MAX_DECISION_BRIEF_OPTIONS

    def test_env_override_cannot_exceed_domain(self, monkeypatch):
        # le= bound rejects an override above the domain cap at construction time.
        monkeypatch.setenv("DECISION_BRIEF_MAX_OPTIONS", "999")
        with pytest.raises(ValidationError):
            DecisionBriefSettings()


class TestChecklistDefensiveOrder:
    def test_non_integer_order_does_not_discard_json(self):
        raw = json.dumps({
            "title": "Procedimiento",
            "items": [
                {"section": "A", "order": "no-es-numero", "text": "Paso uno"},
                {"section": "A", "order": 2, "text": "Paso dos"},
            ],
        })
        title, _desc, items = _parse_llm_output(raw, ChecklistSettings(_env_file=None))
        # Structured parse survived (title kept, not the line-by-line fallback title).
        assert title == "Procedimiento"
        assert [i.text for i in items] == ["Paso uno", "Paso dos"]
        assert items[0].order == 1  # bad order coerced to default
        assert items[1].order == 2
