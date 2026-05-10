"""Per-user notification preference views."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notification.api.serializers import (
    ErrorResponseSerializer,
    EventPreferencesEntrySerializer,
    EventPreferenceUpdateSerializer,
    NotificationPreferenceSerializer,
    NotificationPreferenceUpdateSerializer,
)
from apps.notification.events import get_event, is_known_event
from apps.notification.services import preference_service
from core.authorization import AccessControl
from core.authorization.permissions import (
    NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT,
    NOTIFICATION_PREFERENCES_EVENT_TYPES_GET,
    NOTIFICATION_PREFERENCES_GLOBAL_GET,
    NOTIFICATION_PREFERENCES_GLOBAL_PUT,
)
from core.exceptions.base import NotFoundException


@extend_schema(tags=["Preferences"])
class GlobalPreferenceView(APIView):
    @extend_schema(
        summary="Read user global preferences",
        responses={200: NotificationPreferenceSerializer, 401: ErrorResponseSerializer},
    )
    def get(self, request):
        AccessControl.require_permissions(
            request.user, frozenset({NOTIFICATION_PREFERENCES_GLOBAL_GET})
        )
        prefs = preference_service.get_global(request.user.id)
        return Response(NotificationPreferenceSerializer(prefs).data)

    @extend_schema(
        summary="Update user global preferences",
        request=NotificationPreferenceUpdateSerializer,
        responses={200: NotificationPreferenceSerializer, 400: ErrorResponseSerializer, 401: ErrorResponseSerializer},
    )
    def put(self, request):
        AccessControl.require_permissions(
            request.user, frozenset({NOTIFICATION_PREFERENCES_GLOBAL_PUT})
        )
        serializer = NotificationPreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        prefs = preference_service.upsert_global(
            user_id=request.user.id,
            inapp_enabled=data.get("inapp_enabled"),
            email_enabled=data.get("email_enabled"),
            mute_until=data.get("mute_until") if data.get("mute_until") is not None else None,
            clear_mute=("mute_until" in data and data["mute_until"] is None),
            quiet_hours_start=data.get("quiet_hours_start"),
            quiet_hours_end=data.get("quiet_hours_end"),
            clear_quiet_hours=(
                "quiet_hours_start" in data
                and data["quiet_hours_start"] is None
                and "quiet_hours_end" in data
                and data["quiet_hours_end"] is None
            ),
            quiet_hours_tz=data.get("quiet_hours_tz"),
            updated_by=request.user.id,
        )
        return Response(NotificationPreferenceSerializer(prefs).data)


@extend_schema(tags=["Preferences"])
class EventPreferenceListView(APIView):
    @extend_schema(
        summary="List user event-type preferences with effective values",
        responses={
            200: EventPreferencesEntrySerializer(many=True),
            401: ErrorResponseSerializer,
        },
    )
    def get(self, request):
        AccessControl.require_permissions(
            request.user, frozenset({NOTIFICATION_PREFERENCES_EVENT_TYPES_GET})
        )
        catalogue = preference_service.event_catalogue_for(request.user.id)
        return Response(catalogue)


@extend_schema(tags=["Preferences"])
class EventPreferenceDetailView(APIView):
    @extend_schema(
        summary="Update an event-type preference for the current user",
        request=EventPreferenceUpdateSerializer,
        responses={
            200: EventPreferencesEntrySerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def put(self, request, event_type: str):
        AccessControl.require_permissions(
            request.user, frozenset({NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT})
        )
        if not is_known_event(event_type):
            raise NotFoundException("Unknown event_type.", error_code="event_type_not_found")
        event = get_event(event_type)

        serializer = EventPreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for channel, enabled in serializer.to_channel_pairs():
            preference_service.set_event_preference(
                user_id=request.user.id,
                event_type=event_type,
                channel=channel,
                enabled=enabled,
            )

        overrides = preference_service.event_override_map(request.user.id)
        entry = event.to_public_dict()
        entry["channels"] = {
            channel: overrides.get(
                (event.event_type, channel),
                channel in event.default_channels,
            )
            for channel in event.available_channels
        }
        return Response(entry)
