"""Vistas del admin para elevar y bajar privilegios."""

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from apps.accounts.admin_parts.common import _is_admin_or_super_user, log_audit, has_permission
from apps.accounts.services.elevation_service import (
    drop_elevation,
    elevate_to_superadmin,
    is_elevated,
)


class ElevateForm(forms.Form):
    password = forms.CharField(
        label='Contraseña de Superadmin',
        widget=forms.PasswordInput(render_value=False),
    )


def _elevate_view(request):
    if not has_permission(request, 'ADMIN_ELEVATE'):
        raise PermissionDenied

    if is_elevated(request):
        return redirect(reverse('admin:index'))

    form = ElevateForm(request.POST or None)
    error = None

    if request.method == 'POST' and form.is_valid():
        success = elevate_to_superadmin(request, form.cleaned_data['password'])
        if success:
            log_audit(
                actor=request.user,
                action='ELEVATION_START',
                entity_type='Session',
                entity_label=f'{request.user.username} elevó privilegios a superadmin',
                source='admin',
            )
            return redirect(reverse('admin:index'))
        log_audit(
            actor=request.user,
            action='ELEVATION_FAILED',
            entity_type='Session',
            entity_label=f'{request.user.username} intentó elevar privilegios (contraseña incorrecta)',
            source='admin',
        )
        error = 'Contraseña incorrecta.'

    context = {
        **admin.site.each_context(request),
        'title': 'Acceder como Superadmin',
        'form': form,
        'error': error,
    }
    return TemplateResponse(request, 'admin/elevation/elevate.html', context)


def _drop_elevation_view(request):
    if request.method != 'POST':
        return redirect(reverse('admin:index'))

    real_username = request.user.username
    drop_elevation(request)
    log_audit(
        actor=request.user,
        action='ELEVATION_END',
        entity_type='Session',
        entity_label=f'{real_username} cerró sesión de superadmin',
        source='admin',
    )
    return redirect(reverse('admin:index'))


_prev_get_urls = admin.site.get_urls


def _elevation_get_urls(self):
    urls = _prev_get_urls()
    custom_urls = [
        path('elevate/', self.admin_view(_elevate_view), name='elevate'),
        path('drop-elevation/', self.admin_view(_drop_elevation_view), name='drop_elevation'),
    ]
    return custom_urls + urls


admin.site.get_urls = _elevation_get_urls.__get__(admin.site, admin.AdminSite)
