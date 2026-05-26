import logging

logger = logging.getLogger(__name__)


def log_audit(actor, action: str, entity_type: str,
              entity_id=None, entity_label: str = None,
              details: dict = None, source: str = 'admin',
              elevated_by: str = None) -> None:
    from accounts.models import AuditLog
    try:
        AuditLog.objects.create(
            actor_id=getattr(actor, 'pk', None) if actor else None,
            actor_username=getattr(actor, 'username', str(actor)) if actor else None,
            action=action.upper(),
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            entity_label=entity_label,
            details=details,
            source=source,
            elevated_by=elevated_by,
        )
    except Exception as exc:
        # Audit failures must NEVER break the main operation.
        logger.error('log_audit failed: %s', exc, exc_info=True)


def apply_audit_fields(obj, actor, is_create: bool) -> None:
    if is_create:
        if hasattr(obj, 'created_by_id'):
            if not obj.created_by_id:
                obj.created_by = actor
        else:
            if not obj.created_by:
                obj.created_by = getattr(actor, 'pk', actor)

    if hasattr(obj, 'updated_by_id'):
        obj.updated_by = actor
    else:
        obj.updated_by = getattr(actor, 'pk', actor)
