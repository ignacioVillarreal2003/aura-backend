"""Sincroniza nivel y compartimentos desde LDAP hacia el servicio MAC en cada login.

LDAP es la fuente de verdad y pisa los cambios hechos a mano en el panel. Si el
servicio MAC falla no se corta el login, solo se registra el error en el log.
"""

import logging

from django.conf import settings
from django_auth_ldap.backend import populate_user

logger = logging.getLogger(__name__)


def _sync_mac_attributes(sender, user, ldap_user, **kwargs):
    """Se dispara despues de cada login LDAP exitoso."""
    try:
        _sync_user_role(user, ldap_user)
    except Exception as exc:
        logger.error("LDAP role sync failed for '%s': %s", user.username, exc)

    attrs = ldap_user.attrs

    level_attr       = getattr(settings, 'LDAP_ATTR_CLASSIFICATION_LEVEL', 'auraClassificationLevel')
    compartment_attr = getattr(settings, 'LDAP_ATTR_COMPARTMENT', 'auraCompartment')

    level_name        = _first(attrs.get(level_attr, []))
    compartment_names = list(attrs.get(compartment_attr, []))

    if not level_name and not compartment_names:
        logger.debug(
            "User '%s' has no MAC attributes in LDAP — skipping sync.", user.username
        )
        return

    logger.info(
        "Syncing MAC for '%s': level=%s compartments=%s",
        user.username, level_name, compartment_names,
    )

    try:
        _sync_clearance(user, level_name)
    except Exception as exc:
        logger.error("MAC clearance sync failed for '%s': %s", user.username, exc)

    try:
        _sync_compartments(user, compartment_names)
    except Exception as exc:
        logger.error("MAC compartment sync failed for '%s': %s", user.username, exc)


def _sync_user_role(user, ldap_user) -> None:
    """Sincroniza el rol del usuario desde LDAP basado en LDAP_ATTR_ROLE."""
    from apps.accounts.models import Role, UserRole
    from django.utils import timezone

    role_attr = getattr(settings, 'LDAP_ATTR_ROLE', 'employeeType')
    admin_val = getattr(settings, 'LDAP_ROLE_ADMIN_VALUE', 'admin')

    role_values = ldap_user.attrs.get(role_attr, [])
    is_admin = any(str(val).strip().lower() == admin_val.lower() for val in role_values)

    target_role_name = 'admin' if is_admin else 'user'

    if target_role_name == 'superadmin':
        target_role_name = 'user'

    target_role = Role.objects.filter(name=target_role_name).first()
    if not target_role:
        logger.error("Target role '%s' not found in database.", target_role_name)
        return

    active_roles = UserRole.objects.filter(user=user, deleted_at__isnull=True)
    for active_role in active_roles:
        if active_role.role.name == 'superadmin':
            continue
        if active_role.role_id != target_role.id:
            active_role.deleted_at = timezone.now()
            active_role.deleted_by = user
            active_role.save()
            logger.info("Deactivated role '%s' for LDAP user '%s'", active_role.role.name, user.username)

    has_role = UserRole.objects.filter(user=user, role=target_role, deleted_at__isnull=True).exists()
    if not has_role:
        UserRole.objects.create(
            user=user,
            role=target_role,
            created_by=user
        )
        logger.info("Assigned role '%s' to LDAP user '%s'", target_role_name, user.username)



def _first(lst):
    return lst[0] if lst else None


def _sync_clearance(user, level_name: str | None) -> None:
    """Sincroniza el nivel de clasificación del entry LDAP hacia MAC."""
    if not level_name:
        return

    from apps.accounts.services.mac_client import mac_client

    levels = mac_client.list_classification_levels(user=None)
    match  = next((l for l in levels if l['name'].lower() == level_name.lower()), None)

    if match:
        mac_client.set_user_clearance(None, user.pk, match['id'])
        logger.info(
            "Set clearance for '%s' → '%s' (id=%s)",
            user.username, level_name, match['id'],
        )
    else:
        logger.warning(
            "LDAP clearance '%s' not found in MAC for '%s'. Available: %s",
            level_name, user.username, [l['name'] for l in levels],
        )


def _sync_compartments(user, compartment_names: list[str]) -> None:
    """Sincroniza compartimentos del entry LDAP hacia MAC (add + remove)."""
    if not compartment_names:
        return

    from apps.accounts.services.mac_client import mac_client

    all_compartments  = mac_client.list_compartments(user=None)
    current_entries   = mac_client.list_user_compartments(user=None, target_user_id=user.pk)
    current_names_low = {c['compartment']['name'].lower() for c in current_entries}
    ldap_names_low    = {n.lower() for n in compartment_names}

    for name in compartment_names:
        if name.lower() not in current_names_low:
            match = next(
                (c for c in all_compartments if c['name'].lower() == name.lower()),
                None,
            )
            if match:
                mac_client.add_user_compartment(None, user.pk, match['id'])
                logger.info("Added compartment '%s' to '%s'.", name, user.username)
            else:
                logger.warning(
                    "LDAP compartment '%s' not found in MAC for '%s'.",
                    name, user.username,
                )

    for entry in current_entries:
        entry_name = entry['compartment']['name']
        if entry_name.lower() not in ldap_names_low:
            match = next(
                (c for c in all_compartments if c['name'].lower() == entry_name.lower()),
                None,
            )
            if match:
                mac_client.remove_user_compartment(None, user.pk, match['id'])
                logger.info(
                    "Removed compartment '%s' from '%s' (no longer in LDAP).",
                    entry_name, user.username,
                )



def connect_signals() -> None:
    """Conecta la se\u00f1al LDAP. Llamado desde AccountsConfig.ready()."""
    populate_user.connect(_sync_mac_attributes)
    logger.debug("LDAP MAC sync signal connected.")
