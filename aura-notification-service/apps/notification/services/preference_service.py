from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime
from django.utils import timezone

from apps.notification.events import EventDefinition
from apps.notification.models import NotificationPreference, PreferenceChannel

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

    def upsert_global(
        self,
        user_id: int,
        *,
        inapp_enabled: bool | None = None,
        email_enabled: bool | None = None,
        mute_until: datetime | None = None,
        clear_mute: bool = False,
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
        prefs.save()
        return prefs

    def decide(
        self,
        user_id: int,
        event: EventDefinition,
        channel: str,
        *,
        prefs: NotificationPreference | None = None,
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

        if channel in event.default_channels:
            return PreferenceDecision(True, "ok")
        return PreferenceDecision(False, "event_disabled")


preference_service = PreferenceService()
