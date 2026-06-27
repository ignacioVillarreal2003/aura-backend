"""Utilidades comunes del admin de la app accounts."""

from apps.accounts.admin_parts.utils.filters import CreatedDateFilter, StatusFilter
from apps.accounts.admin_parts.utils.audit import (
    _apply_audit_fields,
    _is_super_admin_user,
    _is_admin_user,
    _is_admin_or_super_user,
    _is_effective_superadmin,
    log_audit,
)
from apps.accounts.admin_parts.utils.mixins import HelpTextStripInlineMixin, HelpTextStripMixin
from apps.accounts.admin_parts.utils.permissions import has_permission

__all__ = [
    'CreatedDateFilter',
    'StatusFilter',
    '_apply_audit_fields',
    '_is_super_admin_user',
    '_is_admin_user',
    '_is_admin_or_super_user',
    '_is_effective_superadmin',
    'log_audit',
    'HelpTextStripInlineMixin',
    'HelpTextStripMixin',
    'has_permission',
]
