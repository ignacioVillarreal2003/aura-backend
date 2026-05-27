"""Privilege elevation service — allows admins to temporarily gain superadmin capabilities."""

from django.conf import settings
from django.utils import timezone

ELEVATION_SESSION_KEY = 'elevated_as_superadmin'
REAL_USER_SESSION_KEY = 'elevation_real_user_id'
ELEVATION_START_KEY = 'elevation_started_at'


def elevate_to_superadmin(request, superadmin_password: str) -> bool:
    """
    Validates the superadmin password. If correct, marks the session as elevated.
    The caller's own user identity is preserved; only the session flags change.
    Returns True if elevation succeeded.
    """
    from accounts.models import User
    from django.contrib.auth.hashers import check_password as django_check_password

    superadmin_username = getattr(settings, 'SUPERADMIN_USERNAME', 'superadmin')
    try:
        superadmin = User.objects.get(
            username=superadmin_username,
            deleted_at__isnull=True,
        )
    except User.DoesNotExist:
        return False

    if not django_check_password(superadmin_password, superadmin.password):
        return False

    request.session[ELEVATION_SESSION_KEY] = True
    request.session[REAL_USER_SESSION_KEY] = request.user.pk
    request.session[ELEVATION_START_KEY] = timezone.now().isoformat()
    request.session.modified = True
    return True


def drop_elevation(request) -> None:
    """Removes elevation keys from the session."""
    for key in (ELEVATION_SESSION_KEY, REAL_USER_SESSION_KEY, ELEVATION_START_KEY):
        request.session.pop(key, None)
    request.session.modified = True


def is_elevated(request) -> bool:
    """Returns True if the current session is in elevated mode and has not timed out."""
    if not request.session.get(ELEVATION_SESSION_KEY):
        return False

    timeout_minutes = getattr(settings, 'ELEVATION_TIMEOUT_MINUTES', 60)
    started_at_iso = request.session.get(ELEVATION_START_KEY)
    if not started_at_iso:
        return False

    try:
        from datetime import datetime, timezone as dt_timezone
        started_at = datetime.fromisoformat(started_at_iso)
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=dt_timezone.utc)
        elapsed = (timezone.now() - started_at).total_seconds() / 60
        if elapsed > timeout_minutes:
            drop_elevation(request)
            try:
                from accounts.admin_parts.utils.audit import log_audit
                log_audit(
                    actor=request.user,
                    action='ELEVATION_END',
                    entity_type='Session',
                    entity_label=f'{request.user.username} finalizó elevación (tiempo agotado)',
                    details={'reason': 'timeout'},
                    source='admin',
                )
            except Exception:
                pass
            return False
    except (ValueError, TypeError):
        drop_elevation(request)
        return False

    return True


def close_stale_elevation(user) -> None:
    """
    Called on login. If this user had an active elevation that was never formally
    ended (session expired or browser was closed), log ELEVATION_END automatically.
    """
    try:
        from accounts.models import AuditLog
        last_start = AuditLog.objects.filter(
            actor_id=user.pk,
            action='ELEVATION_START',
        ).order_by('-timestamp').first()

        if not last_start:
            return

        has_end = AuditLog.objects.filter(
            actor_id=user.pk,
            action='ELEVATION_END',
            timestamp__gt=last_start.timestamp,
        ).exists()

        if not has_end:
            from accounts.admin_parts.utils.audit import log_audit
            log_audit(
                actor=user,
                action='ELEVATION_END',
                entity_type='Session',
                entity_label=f'{user.username} finalizó elevación (sesión expirada)',
                details={'reason': 'session_expired'},
                source='admin',
            )
    except Exception:
        pass


def get_real_user(request):
    """Returns the real admin user even during elevation (always the logged-in user)."""
    return request.user
