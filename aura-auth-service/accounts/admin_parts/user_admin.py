"""User admin configuration."""

import json
import logging

from django.contrib import admin, messages
from django.db.models import F, Q
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

logger = logging.getLogger(__name__)
from accounts.models import User, Role, UserRole
from accounts.admin_parts.common import (
    StatusFilter,
    CreatedDateFilter,
    HelpTextStripMixin,
    _apply_audit_fields,
    _is_super_admin_user,
    _is_admin_or_super_user,
    log_audit,
)
from accounts.admin_parts.forms.user_form import UserAdminForm


@admin.register(User)
class UserAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """
    Custom admin for User model.
    """

    class RoleFilter(admin.SimpleListFilter):
        title = 'Rol'
        parameter_name = 'rol'

        def lookups(self, request, model_admin):
            roles = Role.objects.order_by('name').values_list('name', flat=True)
            return [(name, name) for name in roles]

        def queryset(self, request, queryset):
            value = self.value()
            if not value:
                return queryset
            return queryset.filter(
                user_roles__role__name=value,
                user_roles__deleted_at__isnull=True,
            )

    list_display = (
        'username',
        'email',
        'roles_display',
        'status_badge',
        'created_date',
        'last_login_display',
    )
    list_filter = (
        RoleFilter,
        StatusFilter,
        ('created_at', CreatedDateFilter),
    )
    search_fields = ('username', 'email')
    readonly_fields = (
        'id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
        'last_login',
        'last_password_change',
    )

    form = UserAdminForm
    change_form_template = 'admin/accounts/user/change_form.html'
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Identidad', {
            'fields': ('roles', 'username', 'email', 'password', 'active'),
        }),
    )

    def status_badge(self, obj):
        if obj.is_deleted:
            return format_html(
                '<span style="color: red; font-weight: bold;">&#10007; Eliminado</span>'
            )
        if obj.status == 'active':
            return format_html(
                '<span style="color: green; font-weight: bold;">&#10003; Activo</span>'
            )
        return format_html(
            '<span style="color: #d96c6c; font-weight: bold;">&#x2753; Inactivo</span>'
        )
    status_badge.short_description = 'Estado'

    def roles_display(self, obj):
        if obj.is_deleted:
            roles = obj.user_roles.values_list('role__name', flat=True).distinct()
        else:
            roles = obj.user_roles.filter(deleted_at__isnull=True).values_list('role__name', flat=True)
        labels = []
        for role in roles:
            if role == 'user':
                labels.append('user')
            else:
                labels.append(role)
        return ', '.join(labels) if labels else '-'
    roles_display.short_description = 'Rol'

    def created_date(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y')
        return '-'
    created_date.short_description = 'Creado'
    created_date.admin_order_field = 'created_at'

    def created_by_display(self, obj):
        if obj.is_superuser and obj.created_by and obj.created_by.is_superuser:
            return 'Administracion'
        if obj.created_by:
            return obj.created_by.username
        return '-'
    created_by_display.short_description = 'Creado por'
    created_by_display.admin_order_field = 'created_by__username'

    def last_login_display(self, obj):
        if obj.last_login:
            return obj.last_login.strftime('%d/%m/%Y %H:%M')
        return '-'
    last_login_display.short_description = 'Ultimo login'
    last_login_display.admin_order_field = 'last_login'

    def mac_profile_link(self, obj):
        url = reverse('admin:mac_user_mac', args=[obj.pk])
        return format_html(
            '<a href="{}" style="'
            'display:inline-block;padding:3px 9px;background:#205067;color:#fff;'
            'border-radius:4px;font-size:11px;font-weight:600;text-decoration:none;'
            '">MAC</a>',
            url,
        )
    mac_profile_link.short_description = 'Perfil MAC'
    mac_profile_link.allow_tags = True

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('username', 'email', 'roles_display')
        return self.readonly_fields

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['is_superadmin'] = _is_super_admin_user(request.user)
        return super().changelist_view(request, extra_context=extra_context)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            role_type = request.GET.get('role', 'user')
            if role_type == 'user':
                return (
                    ('Identidad', {
                        'fields': ('username', 'email', 'password', 'active'),
                    }),
                    ('Grupos', {
                        'fields': ('classification_level_id',),
                    }),
                )
            return (
                ('Identidad', {
                    'fields': ('username', 'email', 'password', 'active'),
                }),
            )
        if _is_super_admin_user(request.user):
            return (
                ('Identidad', {
                    'fields': ('roles_display', 'username', 'email', 'active'),
                }),
                ('Grupos', {
                    'fields': ('classification_level_id',),
                }),
                ('Auditoría', {
                    'fields': (
                        'created_by',
                        'created_at',
                        'updated_by',
                        'updated_at',
                        'last_login',
                        'last_password_change',
                        'deleted_by',
                        'deleted_at',
                    ),
                }),
            )
        return (
            ('Identidad', {
                'fields': ('roles_display', 'username', 'email', 'active'),
            }),
        )

    def get_form(self, request, obj=None, **kwargs):
        from django import forms as dj_forms
        from accounts.services.mac_client import mac_client

        form = super().get_form(request, obj, **kwargs)
        for field_name in ('created_by', 'updated_by', 'deleted_by'):
            if field_name in form.base_fields:
                form.base_fields.pop(field_name)
        for field_name in ('username', 'email'):
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = ''

        if obj:
            for field_name in ('roles', 'password', 'compartment_ids'):
                form.base_fields.pop(field_name, None)
            audit_labels = {
                'created_by': 'Creado por',
                'created_at': 'Fecha creado',
                'updated_by': 'Actualizado por',
                'updated_at': 'Fecha actualizado',
                'last_login': 'Ultimo inicio de sesion',
                'last_password_change': 'Ultimo cambio de contrasena',
                'deleted_by': 'Eliminado por',
                'deleted_at': 'Fecha eliminado',
            }
            for field_name, label in audit_labels.items():
                if field_name in form.base_fields:
                    form.base_fields[field_name].label = label
            if _is_super_admin_user(request.user):
                choices = getattr(request, '_mac_level_choices', [('', '-- Sin nivel --')])
                initial = getattr(request, '_mac_current_level_id', '')
                form.base_fields['classification_level_id'] = dj_forms.ChoiceField(
                    choices=choices,
                    required=False,
                    label='Nivel',
                    initial=initial,
                )
            else:
                form.base_fields.pop('classification_level_id', None)
        else:
            # Role is determined by URL param — remove the radio field
            form.base_fields.pop('roles', None)

            role_type = request.GET.get('role', 'user')
            if role_type == 'user':
                try:
                    levels = sorted(
                        mac_client.list_classification_levels(request.user),
                        key=lambda x: x.get('rank', 0),
                    )
                except Exception:
                    levels = []
                try:
                    compartments = mac_client.list_compartments(request.user)
                except Exception:
                    compartments = []
                form.base_fields['classification_level_id'] = dj_forms.ChoiceField(
                    choices=[('', '-- Sin nivel --')] + [
                        (str(l['id']), l['name']) for l in levels
                    ],
                    required=False,
                    label='Nivel',
                )
                form.base_fields.pop('compartment_ids', None)
            else:
                form.base_fields.pop('classification_level_id', None)
                form.base_fields.pop('compartment_ids', None)

        return form

    def get_list_filter(self, request):
        return self.list_filter

    def get_queryset(self, request):
        from datetime import timedelta
        one_week_ago = timezone.now() - timedelta(days=7)
        queryset = super().get_queryset(request)
        return (
            queryset
            .filter(Q(deleted_at__isnull=True) | Q(deleted_at__gte=one_week_ago))
            .prefetch_related('user_roles__role')
            .order_by(F('deleted_at').asc(nulls_first=True), 'username')
        )

    def has_add_permission(self, request):
        if _is_admin_or_super_user(request.user):
            return True
        return bool(request.user and request.user.is_staff)

    def has_module_permission(self, request):
        if _is_admin_or_super_user(request.user):
            return True
        return bool(request.user and request.user.is_staff)

    def has_view_permission(self, request, obj=None):
        if _is_admin_or_super_user(request.user):
            return True
        if obj is None:
            return bool(request.user and request.user.is_staff)
        return bool(request.user and request.user.is_staff)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_deleted:
            return False
        if _is_admin_or_super_user(request.user):
            return True
        if obj is None:
            return bool(request.user and request.user.is_staff)
        return bool(request.user and request.user.is_staff)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_deleted:
            return False
        if _is_admin_or_super_user(request.user):
            return True
        if obj is None:
            return False
        return bool(request.user and request.user.is_staff)

    class Media:
        js = ('accounts/admin/user_password.js', 'accounts/admin/user_form.js')

        css = {
            "all": ("admin/custom.css",)
        }

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if request.GET.get('role') == 'admin':
            extra_context['custom_verbose_name'] = 'Administrador'
        if request.GET.get('role', 'user') == 'user':
            from accounts.services.mac_client import mac_client
            try:
                compartments = mac_client.list_compartments(request.user)
            except Exception:
                compartments = []
            extra_context['compartments_json'] = json.dumps([
                {'id': str(c['id']), 'label': c['name']}
                for c in compartments
            ])
            extra_context['assigned_comp_ids_json'] = json.dumps([])
            extra_context['show_compartments_panel'] = True
        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            if UserRole.objects.filter(
                user_id=int(object_id),
                role__name='admin',
                deleted_at__isnull=True,
            ).exists():
                extra_context['custom_verbose_name'] = 'Administrador'
        except (ValueError, Exception):
            pass

        if object_id and _is_super_admin_user(request.user):
            from accounts.services.mac_client import mac_client, MacServiceError
            try:
                levels = sorted(
                    mac_client.list_classification_levels(request.user),
                    key=lambda x: x.get('rank', 0),
                )
            except MacServiceError:
                levels = []
            try:
                all_compartments = mac_client.list_compartments(request.user)
            except MacServiceError:
                all_compartments = []
            try:
                auth_data = mac_client.get_user_authorization(request.user, int(object_id))
            except MacServiceError:
                auth_data = {}
            clearance = auth_data.get('clearance') if auth_data else None
            user_compartments = auth_data.get('compartments', []) if auth_data else []
            current_level_id = (
                str(clearance['classification_level']['id'])
                if clearance and clearance.get('classification_level')
                else ''
            )
            assigned_comp_ids = [
                str(uc.get('compartment', {}).get('id'))
                for uc in user_compartments
                if uc.get('compartment', {}).get('id')
            ]
            request._mac_level_choices = (
                [('', '-- Sin nivel --')] + [(str(l['id']), l['name']) for l in levels]
            )
            request._mac_current_level_id = current_level_id
            extra_context.update({
                'compartments_json': json.dumps([
                    {'id': str(c['id']), 'label': c['name']}
                    for c in all_compartments
                ]),
                'assigned_comp_ids_json': json.dumps(assigned_comp_ids),
                'show_compartments_panel': True,
            })

        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        if 'active' in form.cleaned_data:
            obj.status = 'active' if form.cleaned_data['active'] else 'inactive'
        _apply_audit_fields(obj, request.user, is_create=not change)
        super().save_model(request, obj, form, change)
        action = 'UPDATE' if change else 'CREATE'
        details = {'changed_fields': form.changed_data} if change and form.changed_data else None
        log_audit(
            actor=request.user,
            action=action,
            entity_type='auth_user',
            entity_id=obj.pk,
            entity_label=obj.username,
            details=details,
        )
        if not change:
            from accounts.services.mac_client import mac_client
            role_type = request.GET.get('role', 'user')
            if role_type == 'admin' and not _is_super_admin_user(request.user):
                role_type = 'user'
            try:
                role = Role.objects.get(name=role_type)
                UserRole.objects.create(user=obj, role=role, created_by=request.user)
            except Role.DoesNotExist:
                pass
            if role_type == 'user':
                cl_id = form.cleaned_data.get('classification_level_id', '')
                comp_ids = request.POST.getlist('compartment_ids')
                if cl_id:
                    try:
                        mac_client.set_user_clearance(request.user, obj.pk, int(cl_id))
                    except Exception as exc:
                        logger.warning('Could not set clearance for user %s: %s', obj.pk, exc)
                for comp_id in comp_ids:
                    try:
                        mac_client.add_user_compartment(request.user, obj.pk, int(comp_id))
                    except Exception as exc:
                        logger.warning('Could not add compartment %s for user %s: %s', comp_id, obj.pk, exc)
        elif change and _is_super_admin_user(request.user):
            from accounts.services.mac_client import mac_client, MacServiceError
            cl_id = (form.cleaned_data.get('classification_level_id') or '').strip()
            comp_ids = request.POST.getlist('compartment_ids')
            if cl_id:
                try:
                    mac_client.set_user_clearance(request.user, obj.pk, int(cl_id))
                except Exception as exc:
                    logger.warning('Could not set clearance for user %s: %s', obj.pk, exc)
            else:
                try:
                    mac_client.delete_user_clearance(request.user, obj.pk)
                except Exception:
                    pass
            try:
                auth_data = mac_client.get_user_authorization(request.user, obj.pk)
                current_comp_ids = {
                    uc.get('compartment', {}).get('id')
                    for uc in (auth_data.get('compartments', []) if auth_data else [])
                    if uc.get('compartment', {}).get('id')
                }
            except Exception:
                current_comp_ids = set()
            new_comp_ids = set(int(c) for c in comp_ids if c)
            for cid in new_comp_ids - current_comp_ids:
                try:
                    mac_client.add_user_compartment(request.user, obj.pk, cid)
                except Exception as exc:
                    logger.warning('Could not add compartment %s for user %s: %s', cid, obj.pk, exc)
            for cid in current_comp_ids - new_comp_ids:
                try:
                    mac_client.remove_user_compartment(request.user, obj.pk, cid)
                except Exception as exc:
                    logger.warning('Could not remove compartment %s for user %s: %s', cid, obj.pk, exc)

    def delete_model(self, request, obj):
        # Soft-delete active role assignments before soft-deleting the user.
        UserRole.objects.filter(user=obj, deleted_at__isnull=True).update(
            deleted_at=timezone.now(),
            deleted_by_id=request.user.pk,
        )
        obj.soft_delete(deleted_by=request.user.pk)
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='auth_user',
            entity_id=obj.pk,
            entity_label=obj.username,
        )

    def delete_queryset(self, request, queryset):
        now = timezone.now()
        for obj in queryset:
            UserRole.objects.filter(user=obj, deleted_at__isnull=True).update(
                deleted_at=now,
                deleted_by_id=request.user.pk,
            )
            obj.soft_delete(deleted_by=request.user.pk)
            log_audit(
                actor=request.user,
                action='DELETE',
                entity_type='auth_user',
                entity_id=obj.pk,
                entity_label=obj.username,
            )
