"""Notification admin for aura-auth-service Django admin panel."""

import requests
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.shortcuts import render

from accounts.models import User
from accounts.admin_parts.common import _is_admin_or_super_user, _is_super_admin_user
from notifications.models import (
    Notification,
    NotificationType,
    NotificationStatus,
    IndividualNotification,
    GroupNotification,
    SystemNotification,
)
from notifications.admin.forms import (
    SendNotificationForm,
    SendGroupNotificationForm,
    SendSystemNotificationForm,
)
from notifications.services.notification_client import create_notifications_from_admin


class BaseNotificationAdmin(admin.ModelAdmin):
    """
    Shared admin behavior for notification sections.
    """

    list_display = (
        'id',
        'receiver_display',
        'scope_display',
        'type',
        'status_badge',
        'message_short',
        'created_at',
        'is_deleted_display',
    )
    list_filter = ('target_scope', 'type', 'status', 'created_at', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('message',)
    readonly_fields = ('id', 'read_at', 'created_at', 'updated_at', 'deleted_at', 'deleted_by')
    ordering = ('-created_at',)
    change_list_template = 'admin/notifications/change_list.html'

    # ------------------------------------------------------------------ display helpers

    def receiver_display(self, obj):
        user = User.objects.filter(pk=obj.receiver_id).first()
        return user.username if user else f'user:{obj.receiver_id}'
    receiver_display.short_description = 'Destinatario'

    def scope_display(self, obj):
        if obj.target_scope == 'group':
            return 'Grupal'
        if obj.target_scope == 'system':
            return 'Sistema'
        return 'Individual'
    scope_display.short_description = 'Alcance'

    def message_short(self, obj):
        return obj.message[:80] + ('…' if len(obj.message) > 80 else '')
    message_short.short_description = 'Mensaje'

    def status_badge(self, obj):
        colours = {'unread': 'green', 'read': '#888', 'archived': 'navy'}
        colour = colours.get(obj.status, 'black')
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colour,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Estado'

    def is_deleted_display(self, obj):
        if obj.deleted_at:
            return format_html('<span style="color:red;">&#10007; Eliminada</span>')
        return format_html('<span style="color:green;">&#10003;</span>')
    is_deleted_display.short_description = 'Activa'

    # ------------------------------------------------------------------ permissions

    def has_add_permission(self, request):
        return False  # Use "Enviar notificación" custom view instead

    def has_module_permission(self, request):
        return _is_admin_or_super_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    # ------------------------------------------------------------------ soft delete

    def delete_model(self, request, obj):
        obj.soft_delete(deleted_by=request.user.pk)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.soft_delete(deleted_by=request.user.pk)

    # ------------------------------------------------------------------ custom "send notification" view

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'send/',
                self.admin_site.admin_view(self.send_notification_view),
                name=f'notifications_{self.model._meta.model_name}_send',
            ),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['send_url'] = reverse(f'admin:notifications_{self.model._meta.model_name}_send')
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(IndividualNotification)
class IndividualNotificationAdmin(BaseNotificationAdmin):
    """Admin section: Individuales."""

    def get_queryset(self, request):
        return Notification.objects.filter(target_scope='individual').order_by('-created_at')

    def send_notification_view(self, request):
        if not _is_admin_or_super_user(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        if request.method == 'POST':
            form = SendNotificationForm(request.POST)
            if form.is_valid():
                recipients = form.cleaned_data['recipients']
                message = form.cleaned_data['message']
                notification_type = form.cleaned_data['type']
                receiver_ids = [user.pk for user in recipients]

                try:
                    result = create_notifications_from_admin(
                        receiver_ids=receiver_ids,
                        message=message,
                        notification_type=notification_type or NotificationType.ADMIN,
                        target_scope='individual',
                        target_label='manual_admin_individual',
                        actor_user_id=request.user.pk,
                    )
                    self.message_user(
                        request,
                        f"Se enviaron {result.get('created', 0)} notificación(es) correctamente.",
                    )
                    return HttpResponseRedirect(
                        reverse('admin:notifications_individualnotification_changelist')
                    )
                except requests.RequestException as exc:
                    self.message_user(
                        request,
                        f'Error al enviar notificaciones al servicio: {exc}',
                        level=messages.ERROR,
                    )
        else:
            form = SendNotificationForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Enviar Notificación Individual',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/notifications/send_notification.html', context)


@admin.register(GroupNotification)
class GroupNotificationAdmin(BaseNotificationAdmin):
    """Admin section: Grupales."""

    def get_queryset(self, request):
        return Notification.objects.filter(target_scope='group').order_by('-created_at')

    def send_notification_view(self, request):
        if not _is_admin_or_super_user(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        if request.method == 'POST':
            form = SendGroupNotificationForm(request.POST)
            if form.is_valid():
                target_user_ids = form.resolve_target_user_ids()
                target_label = form.build_target_label()
                message = form.cleaned_data['message']
                try:
                    result = create_notifications_from_admin(
                        receiver_ids=target_user_ids,
                        message=message,
                        notification_type=NotificationType.ADMIN,
                        target_scope='group',
                        target_label=target_label,
                        actor_user_id=request.user.pk,
                    )
                    self.message_user(
                        request,
                        f"Se enviaron {result.get('created', 0)} notificación(es) grupales.",
                    )
                    return HttpResponseRedirect(
                        reverse('admin:notifications_groupnotification_changelist')
                    )
                except requests.RequestException as exc:
                    self.message_user(
                        request,
                        f'Error al enviar notificaciones al servicio: {exc}',
                        level=messages.ERROR,
                    )
        else:
            form = SendGroupNotificationForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Enviar Notificación Grupal',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/notifications/send_notification.html', context)


@admin.register(SystemNotification)
class SystemNotificationAdmin(BaseNotificationAdmin):
    """Admin section: De sistema."""

    def get_queryset(self, request):
        return Notification.objects.filter(type=NotificationType.SYSTEM).order_by('-created_at')

    def send_notification_view(self, request):
        if not _is_admin_or_super_user(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        if request.method == 'POST':
            form = SendSystemNotificationForm(request.POST)
            if form.is_valid():
                message = form.cleaned_data['message']
                recipients = User.objects.filter(status='active', deleted_at__isnull=True)
                receiver_ids = list(recipients.values_list('id', flat=True))
                try:
                    result = create_notifications_from_admin(
                        receiver_ids=receiver_ids,
                        message=message,
                        notification_type=NotificationType.SYSTEM,
                        target_scope='system',
                        target_label='all_active_users',
                        actor_user_id=request.user.pk,
                    )
                    self.message_user(
                        request,
                        f"Se enviaron {result.get('created', 0)} notificación(es) de sistema.",
                    )
                    return HttpResponseRedirect(
                        reverse('admin:notifications_systemnotification_changelist')
                    )
                except requests.RequestException as exc:
                    self.message_user(
                        request,
                        f'Error al enviar notificaciones al servicio: {exc}',
                        level=messages.ERROR,
                    )
        else:
            form = SendSystemNotificationForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Enviar Notificación de Sistema',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/notifications/send_notification.html', context)
