"""Config-level guarantees for the structured generation services: they process
attached documents by default and only retrieve corpus context when asked, and
they wire all four reduction prompts (map + reduce)."""

import pytest

from app.application.services.user_interactions.checklist_service.checklist_service import ChecklistService
from app.application.services.user_interactions.decision_brief_service.decision_brief_service import DecisionBriefService
from app.application.services.user_interactions.lessons_learned_service.lessons_learned_service import (
    LessonsLearnedService,
)
from app.application.services.user_interactions.quiz_service.quiz_service import QuizService
from app.application.services.user_interactions.report_service.report_service import ReportService
from app.application.services.user_interactions.timeline_service.timeline_service import TimelineService

_SERVICES = [
    ChecklistService,
    DecisionBriefService,
    LessonsLearnedService,
    QuizService,
    ReportService,
    TimelineService,
]


@pytest.mark.parametrize("service_cls", _SERVICES)
def test_defaults_process_documents_only(service_cls):
    assert service_cls.default_process_documents is True
    assert service_cls.default_retrieve_context is False


@pytest.mark.parametrize("service_cls", _SERVICES)
def test_has_all_four_reduction_prompts(service_cls):
    for attr in ("map_system_prompt", "map_human_prompt", "reduce_system_prompt", "reduce_human_prompt"):
        value = getattr(service_cls, attr)
        assert isinstance(value, str) and value.strip(), f"{service_cls.__name__}.{attr} empty"


@pytest.mark.parametrize("service_cls", _SERVICES)
def test_reduction_prompts_use_processor_placeholders(service_cls):
    for attr in ("map_human_prompt", "reduce_human_prompt"):
        value = getattr(service_cls, attr)
        assert "{query}" in value and "{fragments}" in value
        assert "{input}" not in value


@pytest.mark.parametrize("service_cls", _SERVICES)
def test_answer_human_prompt_uses_generation_placeholders(service_cls):
    assert "{context}" in service_cls.human_prompt and "{input}" in service_cls.human_prompt
