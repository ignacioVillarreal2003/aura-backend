"""Basic admin for the notification service's own admin panel (development/debugging)."""

from django.contrib import admin
from django.utils.html import format_html
from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'receiver_id', 'type', 'status_badge', 'message_short', 'created_at', 'deleted_at')
    list_filter = ('type', 'status', 'created_at', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('message', 'receiver_id')
    readonly_fields = ('id', 'read_at', 'created_at', 'updated_at')
    ordering = ('-created_at',)

    def message_short(self, obj):
        return obj.message[:80] + ('…' if len(obj.message) > 80 else '')
    message_short.short_description = 'Mensaje'

    def status_badge(self, obj):
        colours = {'unread': 'green', 'read': 'grey', 'archived': 'navy'}
        colour = colours.get(obj.status, 'black')
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', colour, obj.get_status_display())
    status_badge.short_description = 'Estado'

    def delete_model(self, request, obj):
        obj.soft_delete(deleted_by=request.user.pk if request.user.pk else None)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.soft_delete(deleted_by=request.user.pk if request.user.pk else None)


