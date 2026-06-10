"""
Tests for the internal event emission endpoint:
  POST /api/v1/internal/events/
"""
import pytest
from unittest.mock import patch, MagicMock

from apps.notification.services.dispatch_service import DispatchOutcome

_SVC = "apps.notification.api.views.internal_views.notification_service"

VALID_PAYLOAD = {
    "event_type": "chat.member.invited",
    "recipient_ids": [10, 20],
    "actor_id": 5,
    "actor_name": "admin.user",
    "context": {"chat_id": 99},
}

URL = "/api/v1/internal/events/"


def _outcome(receiver_id, notification_id=None, channels=None):
    return DispatchOutcome(
        receiver_id=receiver_id,
        notification_id=notification_id,
        channels=channels or {},
    )


class TestInternalEventEmissionView:
    def test_missing_token_returns_401(self, api_client):
        response = api_client.post(URL, VALID_PAYLOAD, format="json")
        assert response.status_code == 401
        assert response.data["error"] == "unauthorized"

    def test_wrong_token_returns_401(self, api_client, wrong_token_header):
        response = api_client.post(URL, VALID_PAYLOAD, format="json", **wrong_token_header)
        assert response.status_code == 401
        assert response.data["error"] == "unauthorized"

    def test_valid_token_emits_event_and_returns_201(self, api_client, internal_token_header):
        outcomes = [
            _outcome(10, notification_id=101, channels={"inapp": "sent"}),
            _outcome(20, notification_id=102, channels={"inapp": "sent"}),
        ]
        with patch(_SVC) as svc:
            svc.emit_event.return_value = outcomes
            response = api_client.post(
                URL, VALID_PAYLOAD, format="json", **internal_token_header
            )

        assert response.status_code == 201
        assert response.data["event_type"] == "chat.member.invited"

    def test_unknown_event_type_returns_400(self, api_client, internal_token_header):
        payload = {**VALID_PAYLOAD, "event_type": "unknown.event.type"}
        response = api_client.post(URL, payload, format="json", **internal_token_header)
        assert response.status_code == 400

    def test_empty_recipient_ids_returns_400(self, api_client, internal_token_header):
        payload = {**VALID_PAYLOAD, "recipient_ids": []}
        response = api_client.post(URL, payload, format="json", **internal_token_header)
        assert response.status_code == 400

    def test_too_many_recipients_returns_400(self, api_client, internal_token_header):
        payload = {**VALID_PAYLOAD, "recipient_ids": list(range(1, 10002))}
        response = api_client.post(URL, payload, format="json", **internal_token_header)
        assert response.status_code == 400

    def test_response_includes_per_recipient_outcomes(self, api_client, internal_token_header):
        outcomes = [
            _outcome(10, notification_id=1, channels={"inapp": "sent"}),
            _outcome(20, notification_id=2, channels={"inapp": "sent"}),
        ]
        with patch(_SVC) as svc:
            svc.emit_event.return_value = outcomes
            response = api_client.post(
                URL, VALID_PAYLOAD, format="json", **internal_token_header
            )

        assert len(response.data["outcomes"]) == 2
        assert response.data["outcomes"][0]["receiver_id"] == 10
        assert response.data["outcomes"][1]["receiver_id"] == 20

    def test_response_includes_summary_counts(self, api_client, internal_token_header):
        outcomes = [
            _outcome(10, notification_id=5, channels={"inapp": "sent", "email": "pending"}),
        ]
        with patch(_SVC) as svc:
            svc.emit_event.return_value = outcomes
            response = api_client.post(
                URL, VALID_PAYLOAD, format="json", **internal_token_header
            )

        assert "created" in response.data
        assert "skipped" in response.data
        assert "pending_email" in response.data
        assert response.data["pending_email"] == 1

    def test_service_called_with_correct_event_params(self, api_client, internal_token_header):
        outcomes = [_outcome(10, notification_id=1, channels={"inapp": "sent"})]
        with patch(_SVC) as svc:
            svc.emit_event.return_value = outcomes
            api_client.post(URL, VALID_PAYLOAD, format="json", **internal_token_header)

            call_kwargs = svc.emit_event.call_args[1]
            assert call_kwargs["event_type"] == "chat.member.invited"
            assert set(call_kwargs["recipient_ids"]) == {10, 20}
            assert call_kwargs["actor_id"] == 5

    def test_missing_event_type_field_returns_400(self, api_client, internal_token_header):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "event_type"}
        response = api_client.post(URL, payload, format="json", **internal_token_header)
        assert response.status_code == 400

    def test_missing_recipient_ids_field_returns_400(self, api_client, internal_token_header):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "recipient_ids"}
        response = api_client.post(URL, payload, format="json", **internal_token_header)
        assert response.status_code == 400

    def test_non_silenceable_event_dispatched_without_mocking(self, api_client, internal_token_header):
        """auth.password.changed is non-silenceable — verify the endpoint accepts it."""
        payload = {
            "event_type": "auth.password.changed",
            "recipient_ids": [42],
            "context": {"recipient_email": "user@example.com"},
        }
        outcomes = [_outcome(42, notification_id=1, channels={"inapp": "sent", "email": "pending"})]
        with patch(_SVC) as svc:
            svc.emit_event.return_value = outcomes
            response = api_client.post(URL, payload, format="json", **internal_token_header)

        assert response.status_code == 201
        assert response.data["event_type"] == "auth.password.changed"
