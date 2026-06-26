"""
Parametrized tests for the structured-generation controllers that share the
StructuredGenerationService pipeline (plus general chat): auth, permissions,
request validation, service-unavailable and happy path for each endpoint.
"""
from contextlib import suppress
from dataclasses import dataclass, field
from unittest.mock import AsyncMock

import pytest

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.dtos.user_interactions.checklist.checklist_response import (
    ChecklistGenerateResponse,
    ChecklistItem,
)
from app.domain.dtos.user_interactions.decision_brief.decision_brief_response import (
    DecisionBriefGenerateResponse,
)
from app.domain.dtos.user_interactions.general_chat.general_chat_response import GeneralChatResponse
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_response import (
    LessonsLearnedGenerateResponse,
)
from app.domain.dtos.user_interactions.quiz.quiz_response import (
    QuizGenerateResponse,
    QuizOption,
    QuizQuestion,
    QuizQuestionType,
)
from app.domain.dtos.user_interactions.report.report_request import ReportType
from app.domain.dtos.user_interactions.report.report_response import ReportGenerateResponse
from app.domain.dtos.user_interactions.timeline.timeline_response import (
    TimelineEvent,
    TimelineGenerateResponse,
)

_MESSAGES = [
    Message(role=MessageRole.human, content="Genera el contenido solicitado."),
    Message(role=MessageRole.assistant, content="Aquí está el resultado."),
]

_BASE_BODY = {
    "messages": [{"role": "human", "content": "Genera el contenido solicitado."}],
    "chat_id": 1,
}

_BODY_LAST_MESSAGE_NOT_HUMAN = {
    **_BASE_BODY,
    "messages": [
        {"role": "human", "content": "Genera el contenido solicitado."},
        {"role": "assistant", "content": "Aquí está el resultado."},
    ],
}


@dataclass(frozen=True)
class EndpointCase:
    name: str
    url: str
    state_attr: str
    method: str
    permission: str
    response: object
    extra_body: dict = field(default_factory=dict)

    @property
    def valid_body(self) -> dict:
        return {**_BASE_BODY, **self.extra_body}


CASES = [
    EndpointCase(
        name="general-chat",
        url="/api/v1/general-chat",
        state_attr="general_chat_service",
        method="execute_general_chat",
        permission="LLM_GENERAL_CHAT",
        response=GeneralChatResponse(
            answer="Respuesta del asistente.",
            messages=_MESSAGES,
            fragments=[],
        ),
    ),
    EndpointCase(
        name="report",
        url="/api/v1/report-generate",
        state_attr="report_service",
        method="generate",
        permission="LLM_REPORT_GENERATE",
        response=ReportGenerateResponse(
            report_type=ReportType.SITREP,
            content="# Informe de situación",
            messages=_MESSAGES,
            fragments=[],
        ),
        extra_body={"report_type": "SITREP"},
    ),
    EndpointCase(
        name="checklist",
        url="/api/v1/checklist-generate",
        state_attr="checklist_service",
        method="generate",
        permission="LLM_CHECKLIST_GENERATE",
        response=ChecklistGenerateResponse(
            title="Checklist de verificación",
            items=[ChecklistItem(section="Preparación", order=1, text="Verificar el equipo.")],
            messages=_MESSAGES,
            fragments=[],
        ),
    ),
    EndpointCase(
        name="timeline",
        url="/api/v1/timeline-generate",
        state_attr="timeline_service",
        method="generate",
        permission="LLM_TIMELINE_GENERATE",
        response=TimelineGenerateResponse(
            title="Cronología de eventos",
            events=[TimelineEvent(title="Inicio de la operación", occurred_label="Día 1")],
            messages=_MESSAGES,
            fragments=[],
        ),
    ),
    EndpointCase(
        name="quiz",
        url="/api/v1/quiz-generate",
        state_attr="quiz_service",
        method="generate",
        permission="LLM_QUIZ_GENERATE",
        response=QuizGenerateResponse(
            title="Cuestionario de evaluación",
            questions=[
                QuizQuestion(
                    question="¿Cuál es la respuesta correcta?",
                    type=QuizQuestionType.SINGLE,
                    options=[
                        QuizOption(text="Opción A", is_correct=True),
                        QuizOption(text="Opción B"),
                    ],
                )
            ],
            messages=_MESSAGES,
            fragments=[],
        ),
    ),
    EndpointCase(
        name="lessons-learned",
        url="/api/v1/lessons-learned-generate",
        state_attr="lessons_learned_service",
        method="generate",
        permission="LLM_LESSONS_LEARNED_GENERATE",
        response=LessonsLearnedGenerateResponse(
            title="Lecciones aprendidas",
            items=[],
            messages=_MESSAGES,
            fragments=[],
        ),
    ),
    EndpointCase(
        name="decision-brief",
        url="/api/v1/decision-brief-generate",
        state_attr="decision_brief_service",
        method="generate",
        permission="LLM_DECISION_BRIEF_GENERATE",
        response=DecisionBriefGenerateResponse(
            title="Brief de decisión",
            options=[],
            messages=_MESSAGES,
            fragments=[],
        ),
    ),
]


@pytest.fixture(params=CASES, ids=lambda c: c.name)
def case(request):
    return request.param


@pytest.fixture
def mocked_service(app, case):
    mock = AsyncMock()
    setattr(app.state, case.state_attr, mock)
    yield mock
    with suppress(AttributeError):
        delattr(app.state, case.state_attr)


class TestAuth:
    def test_missing_auth_returns_401(self, client, case):
        response = client.post(case.url, json=case.valid_body)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, make_auth_headers, case, mocked_service):
        response = client.post(
            case.url, json=case.valid_body, headers=make_auth_headers(permissions=[])
        )
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, make_auth_headers, case, mocked_service):
        wrong = "LLM_AGENT" if case.permission != "LLM_AGENT" else "LLM_GENERAL_CHAT"
        response = client.post(
            case.url, json=case.valid_body, headers=make_auth_headers(permissions=[wrong])
        )
        assert response.status_code == 403


class TestValidation:
    def test_empty_body_returns_422(self, client, auth_headers, case, mocked_service):
        response = client.post(case.url, json={}, headers=auth_headers)
        assert response.status_code == 422

    def test_last_message_not_human_returns_422(self, client, auth_headers, case, mocked_service):
        body = {**case.valid_body, **_BODY_LAST_MESSAGE_NOT_HUMAN}
        response = client.post(case.url, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_zero_chat_id_returns_422(self, client, auth_headers, case, mocked_service):
        body = {**case.valid_body, "chat_id": 0}
        response = client.post(case.url, json=body, headers=auth_headers)
        assert response.status_code == 422


class TestSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, case, mocked_service):
        getattr(mocked_service, case.method).return_value = case.response
        response = client.post(case.url, json=case.valid_body, headers=auth_headers)
        assert response.status_code == 200

    def test_service_receives_authenticated_user(self, client, auth_headers, case, mocked_service):
        getattr(mocked_service, case.method).return_value = case.response
        client.post(case.url, json=case.valid_body, headers=auth_headers)
        method_mock = getattr(mocked_service, case.method)
        assert method_mock.await_count == 1
        assert method_mock.await_args.kwargs["authenticated_user"].id == 42


class TestServiceUnavailable:
    def test_missing_service_returns_503(self, client, auth_headers, case, app):
        original = getattr(app.state, case.state_attr, None)
        try:
            if hasattr(app.state, case.state_attr):
                delattr(app.state, case.state_attr)
            response = client.post(case.url, json=case.valid_body, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                setattr(app.state, case.state_attr, original)
