from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
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
    reason: str


class PreferenceService:
    def get_global(self, user_id: int) -> NotificationPreference:
        try:
            return NotificationPreference.objects.get(pk=user_id)
        except NotificationPreference.DoesNotExist:
            return NotificationPreference(user_id=user_id)

    def get_global_map(self, user_ids: list[int]) -> dict[int, NotificationPreference]:
        rows = {row.user_id: row for row in NotificationPreference.objects.filter(user_id__in=user_ids)}
        for uid in user_ids:
            if uid not in rows:
                rows[uid] = NotificationPreference(user_id=uid)
        return rows

    def event_override_map_bulk(self, user_ids: list[int]) -> dict[int, dict[tuple[str, str], bool]]:
        result: dict[int, dict[tuple[str, str], bool]] = {uid: {} for uid in user_ids}
        for row in NotificationEventPreference.objects.filter(user_id__in=user_ids):
            result[row.user_id][(row.event_type, row.channel)] = row.enabled
        return result

    def list_event_overrides(self, user_id: int) -> list[NotificationEventPreference]:
        return list(NotificationEventPreference.objects.filter(user_id=user_id))

    def event_override_map(self, user_id: int) -> dict[tuple[str, str], bool]:
        return {
            (row.event_type, row.channel): row.enabled
            for row in self.list_event_overrides(user_id)
        }

    def upsert_global(
        self,
        user_id: int,
        *,
        inapp_enabled: bool | None = None,
        email_enabled: bool | None = None,
        mute_until: datetime | None = None,
        clear_mute: bool = False,
        updated_by: int | None = None,
    ) -> NotificationPreference:
        prefs, _ = NotificationPreference.objects.get_or_create(
            pk=user_id,
            defaults={"created_by": updated_by},
        )
        if inapp_enabled is not None:
            prefs.inapp_enabled = inapp_enabled
        if email_enabled is not None:
            prefs.email_enabled = email_enabled
        if clear_mute:
            prefs.mute_until = None
        elif mute_until is not None:
            prefs.mute_until = mute_until
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
        updated_by: int | None = None,
    ) -> NotificationEventPreference:
        if channel not in {PreferenceChannel.INAPP, PreferenceChannel.EMAIL}:
            raise ValueError(f"Unknown channel '{channel}'")
        get_event(event_type)
        row, _ = NotificationEventPreference.objects.update_or_create(
            user_id=user_id,
            event_type=event_type,
            channel=channel,
            defaults={"enabled": enabled, "updated_by": updated_by},
        )
        return row

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

        overrides = overrides if overrides is not None else self.event_override_map(user_id)
        explicit = overrides.get((event.event_type, channel))
        if explicit is not None:
            return PreferenceDecision(explicit, "ok" if explicit else "event_disabled")

        if channel in event.default_channels:
            return PreferenceDecision(True, "ok")
        return PreferenceDecision(False, "event_disabled")

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
