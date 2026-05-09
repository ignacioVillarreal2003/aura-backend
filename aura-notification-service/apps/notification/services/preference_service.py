"""User preference resolution.

This service is the single place that decides whether a notification
should be delivered to a given user through a given channel. It honours,
in order:

1. Events flagged `is_silenceable=False` are always delivered.
2. Global mute (`mute_until`) on `notification_preference`.
3. Global per-channel toggle (`inapp_enabled` / `email_enabled`).
4. Per `(event_type, channel)` toggle in `notification_event_preference`.
5. Default channels declared by the event registry.

It also exposes lightweight CRUD used by the public preferences API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

from apps.notification.events import EventDefinition, get_event, iter_events
from apps.notification.models import (
    NotificationEventPreference,
    NotificationPreference,
    PreferenceChannel,
)

logger = logging.getLogger(__name__)


@dataclass
class PreferenceDecision:
    delivered: bool
    reason: str  # "ok" | "muted" | "channel_disabled" | "event_disabled" | "quiet_hours"


class PreferenceService:
    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------
    def get_global(self, user_id: int) -> NotificationPreference:
        try:
            return NotificationPreference.objects.get(pk=user_id)
        except NotificationPreference.DoesNotExist:
            return NotificationPreference(user_id=user_id)

    def list_event_overrides(self, user_id: int) -> list[NotificationEventPreference]:
        return list(NotificationEventPreference.objects.filter(user_id=user_id))

    def event_override_map(self, user_id: int) -> dict[tuple[str, str], bool]:
        return {
            (row.event_type, row.channel): row.enabled
            for row in self.list_event_overrides(user_id)
        }

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------
    def upsert_global(
        self,
        user_id: int,
        *,
        inapp_enabled: bool | None = None,
        email_enabled: bool | None = None,
        mute_until: datetime | None = None,
        quiet_hours_start: time | None = None,
        quiet_hours_end: time | None = None,
        quiet_hours_tz: str | None = None,
        clear_mute: bool = False,
        clear_quiet_hours: bool = False,
        updated_by: int | None = None,
    ) -> NotificationPreference:
        prefs, _ = NotificationPreference.objects.get_or_create(pk=user_id)
        if inapp_enabled is not None:
            prefs.inapp_enabled = inapp_enabled
        if email_enabled is not None:
            prefs.email_enabled = email_enabled
        if clear_mute:
            prefs.mute_until = None
        elif mute_until is not None:
            prefs.mute_until = mute_until
        if clear_quiet_hours:
            prefs.quiet_hours_start = None
            prefs.quiet_hours_end = None
        else:
            if quiet_hours_start is not None:
                prefs.quiet_hours_start = quiet_hours_start
            if quiet_hours_end is not None:
                prefs.quiet_hours_end = quiet_hours_end
        if quiet_hours_tz is not None:
            prefs.quiet_hours_tz = quiet_hours_tz
        if updated_by is not None:
            prefs.updated_by = updated_by
        prefs.save()
        return prefs

    def set_event_preference(
        self,
        user_id: int,
        event_type: str,
        channel: str,
        enabled: bool,
    ) -> NotificationEventPreference:
        if channel not in {PreferenceChannel.INAPP, PreferenceChannel.EMAIL}:
            raise ValueError(f"Unknown channel '{channel}'")
        get_event(event_type)  # raises if unknown
        row, _ = NotificationEventPreference.objects.update_or_create(
            user_id=user_id,
            event_type=event_type,
            channel=channel,
            defaults={"enabled": enabled},
        )
        return row

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def is_quiet_hours(self, prefs: NotificationPreference, *, now: datetime | None = None) -> bool:
        if not prefs.quiet_hours_start or not prefs.quiet_hours_end:
            return False
        try:
            tz = ZoneInfo(prefs.quiet_hours_tz or "UTC")
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("UTC")
        moment = (now or timezone.now()).astimezone(tz).time()
        start = prefs.quiet_hours_start
        end = prefs.quiet_hours_end
        if start <= end:
            return start <= moment < end
        # Overnight window (e.g. 22:00 -> 07:00)
        return moment >= start or moment < end

    def decide(
        self,
        user_id: int,
        event: EventDefinition,
        channel: str,
        *,
        prefs: NotificationPreference | None = None,
        overrides: dict[tuple[str, str], bool] | None = None,
        now: datetime | None = None,
    ) -> PreferenceDecision:
        if not event.is_silenceable:
            return PreferenceDecision(True, "ok")

        prefs = prefs if prefs is not None else self.get_global(user_id)

        if prefs.mute_until and (now or timezone.now()) < prefs.mute_until:
            return PreferenceDecision(False, "muted")

        global_flag = prefs.inapp_enabled if channel == PreferenceChannel.INAPP else prefs.email_enabled
        if not global_flag:
            return PreferenceDecision(False, "channel_disabled")

        if channel == PreferenceChannel.EMAIL and self.is_quiet_hours(prefs, now=now):
            return PreferenceDecision(False, "quiet_hours")

        overrides = overrides if overrides is not None else self.event_override_map(user_id)
        explicit = overrides.get((event.event_type, channel))
        if explicit is not None:
            return PreferenceDecision(explicit, "ok" if explicit else "event_disabled")

        # No explicit override -> fallback to event default channels.
        if channel in event.default_channels:
            return PreferenceDecision(True, "ok")
        return PreferenceDecision(False, "event_disabled")

    # ------------------------------------------------------------------
    # Helpers used by the API to build the catalogue + user state.
    # ------------------------------------------------------------------
    def event_catalogue_for(self, user_id: int) -> list[dict]:
        overrides = self.event_override_map(user_id)
        catalogue: list[dict] = []
        for event in iter_events():
            entry = event.to_public_dict()
            entry["channels"] = {
                channel: overrides.get(
                    (event.event_type, channel),
                    channel in event.default_channels,
                )
                for channel in event.available_channels
            }
            catalogue.append(entry)
        return catalogue

    @staticmethod
    def channels_for_event(event: EventDefinition) -> Iterable[str]:
        return event.available_channels


preference_service = PreferenceService()
