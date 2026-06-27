"""Registra los modulos del admin de accounts."""

from apps.accounts.admin_parts import user_admin as _user_admin  # noqa: F401
from apps.accounts.admin_parts import rbac_admin as _rbac_admin  # noqa: F401
from apps.accounts.admin_parts import site_config as _site_config  # noqa: F401
from apps.accounts.admin_parts import dashboard_admin as _dashboard_admin  # noqa: F401
from apps.accounts.admin_parts import audit_admin as _audit_admin  # noqa: F401
from apps.notifications.admin import notification_admin as _notification_admin  # noqa: F401
from apps.accounts.admin_parts import mac_admin as _mac_admin  # noqa: F401
from apps.accounts.admin_parts import chat_management_admin as _chat_management_admin  # noqa: F401
from apps.accounts.admin_parts import elevation_admin as _elevation_admin  # noqa: F401
