"""Notification admin for aura-auth-service Django admin panel."""

import json
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html

from accounts.models import User, UserRole
from accounts.admin_parts.common import _is_admin_or_super_user, _is_super_admin_user, _is_effective_superadmin
from accounts.admin_parts.utils.audit import log_audit
from notifications.models import (
    Notification,
    NotificationType,
    IndividualNotification,
    GroupNotification,
    SystemNotification,
)
from notifications.admin.forms import SendNotificationForm, SendGroupNotificationForm
from notifications.services.notification_client import (
    NotificationServiceError,
    create_notifications_from_admin,
)


class BaseNotificationAdmin(admin.ModelAdmin):
    """Shared admin behavior for notification sections."""

    allow_send_notifications = True
    list_display = (
        'receiver_display',
        'sender_display',
        'message_short',
        'status_badge',
        'sent_at_display',
        'read_at_display',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('message',)
    readonly_fields = (
        'receiver_display',
        'sender_display',
        'message',
        'status',
        'target_label',
        'read_at',
        'created_at',
        'updated_at',
        'deleted_at',
        'deleted_by',
    )
    fieldsets = (
        ('Notificación', {
            'fields': ('receiver_display', 'sender_display', 'message', 'status', 'target_label'),
        }),
        ('Fechas', {
            'fields': ('created_at', 'read_at', 'updated_at', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',),
        }),
    )
    ordering = ('-created_at',)
    change_list_template = 'admin/notifications/change_list.html'
    actions = None
    actions_selection_counter = False

    def receiver_display(self, obj):
        user = User.objects.filter(pk=obj.receiver_id).first()
        return user.username if user else f'user:{obj.receiver_id}'
    receiver_display.short_description = 'Destinatario'

    def sender_display(self, obj):
        user = User.objects.filter(pk=obj.created_by).first()
        if user:
            return user.username
        if obj.created_by:
            return f'user:{obj.created_by}'
        return 'Sistema'
    sender_display.short_description = 'Remitente'

    def message_short(self, obj):
        return obj.message[:100] + ('…' if len(obj.message) > 100 else '')
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

    def sent_at_display(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y %H:%M')
        return '-'
    sent_at_display.short_description = 'Enviado el'
    sent_at_display.admin_order_field = 'created_at'

    def read_at_display(self, obj):
        if obj.read_at:
            return obj.read_at.strftime('%d/%m/%Y %H:%M')
        return '-'
    read_at_display.short_description = 'Leído el'
    read_at_display.admin_order_field = 'read_at'

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return _is_admin_or_super_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def delete_model(self, request, obj):
        obj.soft_delete(deleted_by=request.user.pk)
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='Notification',
            entity_id=str(obj.pk),
            entity_label=obj.message[:80],
            details={
                'receiver_id': obj.receiver_id,
                'target_scope': obj.target_scope,
                'deleted_at': str(obj.deleted_at),
            },
            source='admin',
            request=request,
        )

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.soft_delete(deleted_by=request.user.pk)
            log_audit(
                actor=request.user,
                action='DELETE',
                entity_type='Notification',
                entity_id=str(obj.pk),
                entity_label=obj.message[:80],
                details={
                    'receiver_id': obj.receiver_id,
                    'target_scope': obj.target_scope,
                    'deleted_at': str(obj.deleted_at),
                },
                source='admin',
                request=request,
            )

    def get_urls(self):
        urls = super().get_urls()
        if not self.allow_send_notifications:
            return urls
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
        if self.allow_send_notifications:
            extra_context['send_url'] = reverse(f'admin:notifications_{self.model._meta.model_name}_send')
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(IndividualNotification)
class IndividualNotificationAdmin(BaseNotificationAdmin):
    """Admin section: Individuales."""

    def _privileged_user_ids(self):
        """Return a plain list of user IDs that hold admin or superadmin roles."""
        return list(
            UserRole.objects.filter(
                role__name__in=['admin', 'superadmin'],
                deleted_at__isnull=True,
            ).values_list('user_id', flat=True)
        )

    def _recipients_queryset(self, request):
        """Active users the current actor is allowed to target."""
        base = User.objects.filter(deleted_at__isnull=True, status='active')
        if _is_effective_superadmin(request):
            return base.order_by('username')
        return base.exclude(pk__in=self._privileged_user_ids()).order_by('username')

    def get_queryset(self, request):
        qs = Notification.objects.filter(target_scope='individual').order_by('-created_at')
        if not _is_effective_superadmin(request):
            qs = qs.exclude(receiver_id__in=self._privileged_user_ids())
        return qs

    def send_notification_view(self, request):
        if not _is_admin_or_super_user(request.user):
            raise PermissionDenied

        recipients_qs = self._recipients_queryset(request)

        if request.method == 'POST':
            form = SendNotificationForm(request.POST, recipients_queryset=recipients_qs)
            if form.is_valid():
                recipients = form.cleaned_data['recipients']
                message = form.cleaned_data['message']
                receiver_ids = [user.pk for user in recipients]

                try:
                    result = create_notifications_from_admin(
                        receiver_ids=receiver_ids,
                        message=message,
                        notification_type=NotificationType.ADMIN,
                        target_scope='individual',
                        target_label='manual_admin_individual',
                        actor_user_id=request.user.pk,
                    )
                    self.message_user(
                        request,
                        f"Se enviaron {result.get('created', 0)} notificación(es) correctamente.",
                    )
                    log_audit(
                        actor=request.user,
                        action='CREATE',
                        entity_type='Notification',
                        entity_label=f'{request.user.username} envió una notificación individual',
                        details={
                            'receiver_ids': receiver_ids,
                            'message': message,
                            'type': NotificationType.ADMIN,
                            'target_scope': 'individual',
                            'created': result.get('created', 0),
                        },
                        source='admin',
                        request=request,
                    )
                    return HttpResponseRedirect(reverse('admin:notifications_individualnotification_changelist'))
                except NotificationServiceError as exc:
                    self.message_user(request, f'Error al enviar notificaciones al servicio: {exc}', level=messages.ERROR)
        else:
            form = SendNotificationForm(recipients_queryset=recipients_qs)

        users_json = json.dumps([
            {'id': str(user.pk), 'label': f"{user.username} ({user.email})"}
            for user in recipients_qs
        ])

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'opts': self.model._meta,
            'show_search': True,
            'users_json': users_json,
        }
        return render(request, 'admin/notifications/send_notification.html', context)


@admin.register(GroupNotification)
class GroupNotificationAdmin(BaseNotificationAdmin):
    """Admin section: Grupales."""

    def get_queryset(self, request):
        return Notification.objects.filter(target_scope='group').order_by('-created_at')

    def send_notification_view(self, request):
        if not _is_admin_or_super_user(request.user):
            raise PermissionDenied

        from accounts.models import Role
        from accounts.services.mac_client import mac_client, MacServiceError as MacError

        try:
            raw_levels = mac_client.list_classification_levels(request.user)
        except MacError:
            raw_levels = []

        try:
            raw_compartments = mac_client.list_compartments(request.user)
        except MacError:
            raw_compartments = []

        level_choices = [(str(l['id']), f"{l['name']} (rango {l['rank']})") for l in raw_levels]
        compartment_choices = [(str(c['id']), c['name']) for c in raw_compartments]

        if request.method == 'POST':
            form = SendGroupNotificationForm(
                request.POST,
                level_choices=level_choices,
                compartment_choices=compartment_choices,
            )
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
                    log_audit(
                        actor=request.user,
                        action='CREATE',
                        entity_type='Notification',
                        entity_label=f'{request.user.username} envió una notificación grupal',
                        details={
                            'target_label': target_label,
                            'receiver_ids': target_user_ids,
                            'message': message,
                            'type': NotificationType.ADMIN,
                            'target_scope': 'group',
                            'created': result.get('created', 0),
                        },
                        source='admin',
                        request=request,
                    )
                    return HttpResponseRedirect(reverse('admin:notifications_groupnotification_changelist'))
                except NotificationServiceError as exc:
                    self.message_user(request, f'Error al enviar notificaciones al servicio: {exc}', level=messages.ERROR)
        else:
            form = SendGroupNotificationForm(
                level_choices=level_choices,
                compartment_choices=compartment_choices,
            )

        levels_json = json.dumps([
            {'id': str(l['id']), 'label': f"{l['name']} (rango {l['rank']})"} for l in raw_levels
        ])
        compartments_json = json.dumps([
            {'id': str(c['id']), 'label': c['name']} for c in raw_compartments
        ])

        roles_data = Role.objects.filter(name='user')
        roles_json = json.dumps([
            {'id': str(role.pk), 'label': role.name}
            for role in roles_data
        ])

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'opts': self.model._meta,
            'show_search': False,
            'levels_json': levels_json,
            'compartments_json': compartments_json,
            'roles_json': roles_json,
        }
        return render(request, 'admin/notifications/send_notification.html', context)


@admin.register(SystemNotification)
class SystemNotificationAdmin(BaseNotificationAdmin):
    """Admin section: De sistema."""

    allow_send_notifications = False

    def get_queryset(self, request):
        return Notification.objects.filter(type=NotificationType.SYSTEM).order_by('-created_at')
