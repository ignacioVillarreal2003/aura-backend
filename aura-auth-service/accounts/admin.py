"""Register accounts admin modules."""

# Import submodules to register admin classes and site config.
from accounts.admin_parts import user_admin as _user_admin  # noqa: F401
from accounts.admin_parts import rbac_admin as _rbac_admin  # noqa: F401
from accounts.admin_parts import custom_group_admin as _custom_group_admin  # noqa: F401
from accounts.admin_parts import site_config as _site_config  # noqa: F401
from accounts.admin_parts import dashboard_admin as _dashboard_admin  # noqa: F401
from accounts.admin_parts import audit_admin as _audit_admin
from accounts.admin_parts import elevation_admin as _elevation_admin  # noqa: F401  # noqa: F401
from notifications.admin import notification_admin as _notification_admin  # noqa: F401
