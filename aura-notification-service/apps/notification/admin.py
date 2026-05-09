from django.contrib import admin
from django.utils.html import format_html

from apps.notification.models import (
    Notification,
    NotificationDispatch,
    NotificationEventPreference,
    NotificationPreference,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "receiver_id",
        "event_type",
        "type",
        "status_badge",
        "severity",
        "message_short",
        "created_at",
        "deleted_at",
    )
    list_filter = ("type", "event_type", "status", "severity", "created_at")
    search_fields = ("message", "receiver_id", "event_type", "event_key")
    readonly_fields = ("id", "read_at", "created_at", "updated_at")
    ordering = ("-created_at",)

    def message_short(self, obj):
        return obj.message[:80] + ("..." if len(obj.message) > 80 else "")

    message_short.short_description = "Mensaje"

    def status_badge(self, obj):
        colours = {"unread": "green", "read": "grey", "archived": "navy"}
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colours.get(obj.status, "black"),
            obj.get_status_display() if hasattr(obj, "get_status_display") else obj.status,
        )

    status_badge.short_description = "Estado"

    def delete_model(self, request, obj):
        obj.soft_delete(deleted_by=request.user.pk if request.user.pk else None)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.soft_delete(deleted_by=request.user.pk if request.user.pk else None)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user_id",
        "inapp_enabled",
        "email_enabled",
        "mute_until",
        "quiet_hours_start",
        "quiet_hours_end",
        "quiet_hours_tz",
    )
    search_fields = ("user_id",)


@admin.register(NotificationEventPreference)
class NotificationEventPreferenceAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "event_type", "channel", "enabled")
    list_filter = ("channel", "enabled", "event_type")
    search_fields = ("user_id", "event_type")


@admin.register(NotificationDispatch)
class NotificationDispatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "receiver_id",
        "event_type",
        "channel",
        "status",
        "attempt",
        "created_at",
        "sent_at",
    )
    list_filter = ("channel", "status", "event_type")
    search_fields = ("receiver_id", "event_type", "notification_id", "error")
    readonly_fields = ("created_at", "sent_at")
    ordering = ("-created_at",)
