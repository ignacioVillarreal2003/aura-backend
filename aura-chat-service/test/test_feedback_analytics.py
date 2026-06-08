from datetime import timedelta

from django.utils import timezone

from apps.message.services.feedback_analytics_service import FeedbackAnalyticsService


ANALYTICS_VIEW = "apps.message.views.feedback_analytics_view"
ANALYTICS_SVC = "apps.message.services.feedback_analytics_service"


def _sample_analytics():
    now = timezone.now()
    return {
        "window_days": 30,
        "start": now - timedelta(days=30),
        "end": now,
        "summary": {"total": 3, "thumbs_up": 2, "thumbs_down": 1, "satisfaction_rate": 0.6667},
        "assistants": [
            {
                "assistant_id": 5,
                "assistant_name": "Legal",
                "total": 3,
                "thumbs_up": 2,
                "thumbs_down": 1,
                "satisfaction_rate": 0.6667,
            }
        ],
        "reasons": [{"reason": "incomplete", "count": 1}],
        "recent_negative": [
            {
                "id": 9,
                "artifact_id": 42,
                "assistant_id": 5,
                "assistant_name": "Legal",
                "reason": "incomplete",
                "comment": "Faltó algo",
                "user_id": 7,
                "created_at": now,
                "message_excerpt": "respuesta...",
            }
        ],
    }


# ---------------------------------------------------------------------------
# View  GET /api/v1/feedback/analytics/
# ---------------------------------------------------------------------------

def test_analytics_returns_200(api_client, mocker):
    mocker.patch(
        f"{ANALYTICS_VIEW}.feedback_analytics_service.get_analytics",
        return_value=_sample_analytics(),
    )
    response = api_client.get("/api/v1/feedback/analytics/")
    assert response.status_code == 200
    assert response.data["summary"]["thumbs_down"] == 1
    assert response.data["assistants"][0]["assistant_name"] == "Legal"
    assert response.data["reasons"][0]["reason"] == "incomplete"


def test_analytics_forwards_days(api_client, mocker):
    get_analytics = mocker.patch(
        f"{ANALYTICS_VIEW}.feedback_analytics_service.get_analytics",
        return_value=_sample_analytics(),
    )
    response = api_client.get("/api/v1/feedback/analytics/?days=7")
    assert response.status_code == 200
    _, kwargs = get_analytics.call_args
    assert kwargs["days"] == 7


def test_analytics_invalid_days_passes_none(api_client, mocker):
    get_analytics = mocker.patch(
        f"{ANALYTICS_VIEW}.feedback_analytics_service.get_analytics",
        return_value=_sample_analytics(),
    )
    response = api_client.get("/api/v1/feedback/analytics/?days=abc")
    assert response.status_code == 200
    _, kwargs = get_analytics.call_args
    assert kwargs["days"] is None


def test_analytics_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/feedback/analytics/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Service (repository mocked)
# ---------------------------------------------------------------------------

def _user(user_id=1):
    from types import SimpleNamespace
    return SimpleNamespace(id=user_id, permissions={"VIEW_FEEDBACK_ANALYTICS"})


def test_service_assembles_and_resolves_names(mocker):
    mocker.patch(
        "core.authorization.access.AccessControl.require_permissions",
        return_value=None,
    )
    repo = mocker.patch(f"{ANALYTICS_SVC}.feedback_analytics_repository")
    repo.summary.return_value = {"total": 2, "thumbs_up": 1, "thumbs_down": 1}
    repo.per_assistant.return_value = [
        {"assistant_id": 5, "total": 2, "thumbs_up": 1, "thumbs_down": 1},
        {"assistant_id": None, "total": 0, "thumbs_up": 0, "thumbs_down": 0},
    ]
    repo.reason_breakdown.return_value = [{"reason": "tone", "count": 1}]
    repo.recent_negative.return_value = []
    mocker.patch.object(
        FeedbackAnalyticsService, "_resolve_assistant_names", return_value={5: "Legal"}
    )

    result = FeedbackAnalyticsService().get_analytics(_user(), days=30)

    assert result["summary"]["satisfaction_rate"] == 0.5
    by_name = {row["assistant_name"]: row for row in result["assistants"]}
    assert "Legal" in by_name
    assert "Chats sin asistente" in by_name


def test_service_clamps_days(mocker):
    mocker.patch(
        "core.authorization.access.AccessControl.require_permissions",
        return_value=None,
    )
    repo = mocker.patch(f"{ANALYTICS_SVC}.feedback_analytics_repository")
    repo.summary.return_value = {"total": 0, "thumbs_up": 0, "thumbs_down": 0}
    repo.per_assistant.return_value = []
    repo.reason_breakdown.return_value = []
    repo.recent_negative.return_value = []

    result = FeedbackAnalyticsService().get_analytics(_user(), days=99999)

    assert result["window_days"] == 365
    assert result["summary"]["satisfaction_rate"] is None
