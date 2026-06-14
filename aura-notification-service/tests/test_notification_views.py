"""
Tests for notification inbox endpoints:
  GET    /api/v1/notifications/
  GET    /api/v1/notifications/unread-count/
  GET    /api/v1/notifications/<pk>/
  PATCH  /api/v1/notifications/<pk>/
  DELETE /api/v1/notifications/<pk>/
  POST   /api/v1/notifications/mark-all-read/
"""
import pytest
from unittest.mock import MagicMock, patch

from core.exceptions.base import NotFoundException
from core.authorization.permissions import (
    NOTIFICATION_DETAIL_GET,
    NOTIFICATION_INBOX_LIST,
    NOTIFICATION_MARK_ALL_READ_POST,
    NOTIFICATION_SOFT_DELETE,
    NOTIFICATION_STATUS_PATCH,
    NOTIFICATION_UNREAD_COUNT_GET,
)

_SVC = "apps.notification.api.views.notification_views.notification_service"


class _FakeQuerySet:
    """Minimal queryset substitute accepted by Django's Paginator."""
    def __init__(self, items=None):
        self._items = list(items or [])

    def count(self):
        return len(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, key):
        return self._items[key]

    def __iter__(self):
        return iter(self._items)


def _mock_qs(notifications=None):
    return _FakeQuerySet(notifications or [])


class TestNotificationListView:
    URL = "/api/v1/notifications/"

    def test_returns_401_without_auth(self, api_client):
        response = api_client.get(self.URL)
        assert response.status_code == 401

    def test_returns_403_when_permission_missing(self, api_client, auth_headers):
        response = api_client.get(self.URL, **auth_headers(permissions=["WRONG_PERM"]))
        assert response.status_code == 403

    def test_returns_paginated_response_on_success(self, api_client, auth_headers, make_notification):
        notif = make_notification(id=10, status="unread")
        with patch(_SVC) as svc:
            svc.list_for_user.return_value = _mock_qs([notif])
            response = api_client.get(
                self.URL,
                **auth_headers(permissions=[NOTIFICATION_INBOX_LIST]),
            )

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == 10

    def test_empty_inbox_returns_count_zero(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.list_for_user.return_value = _mock_qs([])
            response = api_client.get(
                self.URL,
                **auth_headers(permissions=[NOTIFICATION_INBOX_LIST]),
            )

        assert response.status_code == 200
        assert response.data["count"] == 0
        assert response.data["results"] == []

    def test_filters_by_status_passed_to_service(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.list_for_user.return_value = _mock_qs()
            api_client.get(
                f"{self.URL}?status=unread&status=read",
                **auth_headers(permissions=[NOTIFICATION_INBOX_LIST]),
            )
            _, kwargs = svc.list_for_user.call_args
            assert set(kwargs["status_in"]) == {"unread", "read"}

    def test_filters_by_event_type_passed_to_service(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.list_for_user.return_value = _mock_qs()
            api_client.get(
                f"{self.URL}?event_type=chat.member.invited",
                **auth_headers(permissions=[NOTIFICATION_INBOX_LIST]),
            )
            _, kwargs = svc.list_for_user.call_args
            assert kwargs["event_type"] == "chat.member.invited"

    def test_valid_since_param_is_parsed_and_forwarded(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.list_for_user.return_value = _mock_qs()
            api_client.get(
                f"{self.URL}?since=2024-01-15T10:30:00Z",
                **auth_headers(permissions=[NOTIFICATION_INBOX_LIST]),
            )
            _, kwargs = svc.list_for_user.call_args
            assert kwargs["since"] is not None

    def test_invalid_since_format_returns_400(self, api_client, auth_headers):
        with patch(_SVC):
            response = api_client.get(
                f"{self.URL}?since=not-a-datetime",
                **auth_headers(permissions=[NOTIFICATION_INBOX_LIST]),
            )

        assert response.status_code == 400
        assert response.data["error"] == "invalid_since"

    def test_service_called_with_authenticated_user_id(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.list_for_user.return_value = _mock_qs()
            api_client.get(
                self.URL,
                **auth_headers(user_id=99, permissions=[NOTIFICATION_INBOX_LIST]),
            )
            args, _ = svc.list_for_user.call_args
            assert args[0] == 99


class TestNotificationUnreadCountView:
    URL = "/api/v1/notifications/unread-count/"

    def test_returns_401_without_auth(self, api_client):
        assert api_client.get(self.URL).status_code == 401

    def test_returns_403_when_permission_missing(self, api_client, auth_headers):
        response = api_client.get(self.URL, **auth_headers(permissions=["WRONG_PERM"]))
        assert response.status_code == 403

    def test_returns_unread_count(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.unread_count.return_value = 7
            response = api_client.get(
                self.URL,
                **auth_headers(permissions=[NOTIFICATION_UNREAD_COUNT_GET]),
            )

        assert response.status_code == 200
        assert response.data == {"count": 7}

    def test_returns_zero_when_inbox_is_clean(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.unread_count.return_value = 0
            response = api_client.get(
                self.URL,
                **auth_headers(permissions=[NOTIFICATION_UNREAD_COUNT_GET]),
            )

        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_count_scoped_to_authenticated_user(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.unread_count.return_value = 3
            api_client.get(
                self.URL,
                **auth_headers(user_id=55, permissions=[NOTIFICATION_UNREAD_COUNT_GET]),
            )
            svc.unread_count.assert_called_once_with(55)


class TestNotificationDetailGetView:
    def url(self, pk=1):
        return f"/api/v1/notifications/{pk}/"

    def test_returns_401_without_auth(self, api_client):
        assert api_client.get(self.url()).status_code == 401

    def test_returns_403_when_permission_missing(self, api_client, auth_headers):
        response = api_client.get(self.url(), **auth_headers(permissions=["WRONG_PERM"]))
        assert response.status_code == 403

    def test_returns_notification_data(self, api_client, auth_headers, make_notification):
        notif = make_notification(id=5, status="read", message="Hello world")
        with patch(_SVC) as svc:
            svc.get_for_user.return_value = notif
            response = api_client.get(
                self.url(5),
                **auth_headers(permissions=[NOTIFICATION_DETAIL_GET]),
            )

        assert response.status_code == 200
        assert response.data["id"] == 5
        assert response.data["status"] == "read"
        assert response.data["message"] == "Hello world"

    def test_returns_404_when_notification_not_found(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.get_for_user.side_effect = NotFoundException(
                "Notification not found.", error_code="notification_not_found"
            )
            response = api_client.get(
                self.url(999),
                **auth_headers(permissions=[NOTIFICATION_DETAIL_GET]),
            )

        assert response.status_code == 404
        assert response.data["error"] == "notification_not_found"

    def test_cannot_access_another_users_notification(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.get_for_user.side_effect = NotFoundException(
                "Notification not found.", error_code="notification_not_found"
            )
            response = api_client.get(
                self.url(1),
                **auth_headers(user_id=99, permissions=[NOTIFICATION_DETAIL_GET]),
            )

        assert response.status_code == 404
        svc.get_for_user.assert_called_once_with(99, 1)


class TestNotificationDetailPatchView:
    def url(self, pk=1):
        return f"/api/v1/notifications/{pk}/"

    def test_returns_401_without_auth(self, api_client):
        assert api_client.patch(self.url(), {"status": "read"}, format="json").status_code == 401

    def test_returns_403_when_permission_missing(self, api_client, auth_headers):
        response = api_client.patch(
            self.url(), {"status": "read"}, format="json",
            **auth_headers(permissions=["WRONG_PERM"]),
        )
        assert response.status_code == 403

    def test_marks_notification_as_read(self, api_client, auth_headers, make_notification):
        updated = make_notification(id=1, status="read")
        with patch(_SVC) as svc:
            svc.update_status.return_value = updated
            response = api_client.patch(
                self.url(1), {"status": "read"}, format="json",
                **auth_headers(user_id=42, permissions=[NOTIFICATION_STATUS_PATCH]),
            )

        assert response.status_code == 200
        assert response.data["status"] == "read"
        svc.update_status.assert_called_once_with(42, 1, "read")

    def test_marks_notification_as_unread(self, api_client, auth_headers, make_notification):
        updated = make_notification(id=1, status="unread", read_at=None)
        with patch(_SVC) as svc:
            svc.update_status.return_value = updated
            response = api_client.patch(
                self.url(1), {"status": "unread"}, format="json",
                **auth_headers(permissions=[NOTIFICATION_STATUS_PATCH]),
            )

        assert response.status_code == 200
        assert response.data["status"] == "unread"
        assert response.data["read_at"] is None

    def test_invalid_status_value_returns_400(self, api_client, auth_headers):
        with patch(_SVC):
            response = api_client.patch(
                self.url(1), {"status": "deleted"}, format="json",
                **auth_headers(permissions=[NOTIFICATION_STATUS_PATCH]),
            )

        assert response.status_code == 400

    def test_missing_status_field_returns_400(self, api_client, auth_headers):
        with patch(_SVC):
            response = api_client.patch(
                self.url(1), {}, format="json",
                **auth_headers(permissions=[NOTIFICATION_STATUS_PATCH]),
            )

        assert response.status_code == 400

    def test_not_found_notification_returns_404(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.update_status.side_effect = NotFoundException(
                "Notification not found.", error_code="notification_not_found"
            )
            response = api_client.patch(
                self.url(999), {"status": "read"}, format="json",
                **auth_headers(permissions=[NOTIFICATION_STATUS_PATCH]),
            )

        assert response.status_code == 404
        assert response.data["error"] == "notification_not_found"


class TestNotificationDetailDeleteView:
    def url(self, pk=1):
        return f"/api/v1/notifications/{pk}/"

    def test_returns_401_without_auth(self, api_client):
        assert api_client.delete(self.url()).status_code == 401

    def test_returns_403_when_permission_missing(self, api_client, auth_headers):
        response = api_client.delete(self.url(), **auth_headers(permissions=["WRONG_PERM"]))
        assert response.status_code == 403

    def test_soft_deletes_notification_and_returns_204(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.soft_delete.return_value = None
            response = api_client.delete(
                self.url(3),
                **auth_headers(user_id=42, permissions=[NOTIFICATION_SOFT_DELETE]),
            )

        assert response.status_code == 204
        svc.soft_delete.assert_called_once_with(42, 3)

    def test_not_found_notification_returns_404(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.soft_delete.side_effect = NotFoundException(
                "Notification not found.", error_code="notification_not_found"
            )
            response = api_client.delete(
                self.url(999),
                **auth_headers(permissions=[NOTIFICATION_SOFT_DELETE]),
            )

        assert response.status_code == 404
        assert response.data["error"] == "notification_not_found"

    def test_deleted_notification_returns_no_body(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.soft_delete.return_value = None
            response = api_client.delete(
                self.url(1),
                **auth_headers(permissions=[NOTIFICATION_SOFT_DELETE]),
            )

        assert response.status_code == 204
        assert not response.content


class TestMarkAllReadView:
    URL = "/api/v1/notifications/mark-all-read/"

    def test_returns_401_without_auth(self, api_client):
        assert api_client.post(self.URL, {}, format="json").status_code == 401

    def test_returns_403_when_permission_missing(self, api_client, auth_headers):
        response = api_client.post(
            self.URL, {}, format="json",
            **auth_headers(permissions=["WRONG_PERM"]),
        )
        assert response.status_code == 403

    def test_marks_all_unread_and_returns_count(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.mark_all_read.return_value = 12
            response = api_client.post(
                self.URL, {}, format="json",
                **auth_headers(user_id=42, permissions=[NOTIFICATION_MARK_ALL_READ_POST]),
            )

        assert response.status_code == 200
        assert response.data["updated"] == 12
        svc.mark_all_read.assert_called_once_with(42, until_id=None)

    def test_marks_only_up_to_until_id(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.mark_all_read.return_value = 4
            response = api_client.post(
                self.URL, {"until_id": 200}, format="json",
                **auth_headers(user_id=42, permissions=[NOTIFICATION_MARK_ALL_READ_POST]),
            )

        assert response.status_code == 200
        assert response.data["updated"] == 4
        svc.mark_all_read.assert_called_once_with(42, until_id=200)

    def test_empty_body_is_valid_and_marks_all(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.mark_all_read.return_value = 0
            response = api_client.post(
                self.URL, format="json",
                **auth_headers(permissions=[NOTIFICATION_MARK_ALL_READ_POST]),
            )

        assert response.status_code == 200

    def test_negative_until_id_returns_400(self, api_client, auth_headers):
        with patch(_SVC):
            response = api_client.post(
                self.URL, {"until_id": -5}, format="json",
                **auth_headers(permissions=[NOTIFICATION_MARK_ALL_READ_POST]),
            )

        assert response.status_code == 400

    def test_zero_until_id_returns_400(self, api_client, auth_headers):
        with patch(_SVC):
            response = api_client.post(
                self.URL, {"until_id": 0}, format="json",
                **auth_headers(permissions=[NOTIFICATION_MARK_ALL_READ_POST]),
            )

        assert response.status_code == 400

    def test_returns_zero_when_no_unread_notifications(self, api_client, auth_headers):
        with patch(_SVC) as svc:
            svc.mark_all_read.return_value = 0
            response = api_client.post(
                self.URL, {}, format="json",
                **auth_headers(permissions=[NOTIFICATION_MARK_ALL_READ_POST]),
            )

        assert response.status_code == 200
        assert response.data["updated"] == 0
