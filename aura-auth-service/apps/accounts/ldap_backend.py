"""Custom LDAP authentication backend for the Aura auth service.

Extiende LDAPBackend de django-auth-ldap para integrarse con el esquema
auth_user que tiene particularidades propias:

- FK circular created_by: la primera inserci\u00f3n usa _bootstrap_create_user,
  que hace un INSERT raw resolvi\u00e9ndola v\u00eda currval(seq).
- Campo password NOT NULL: se almacena make_password(None) (\u201c!hash\u201d)
  para usuarios que no tienen contrase\u00f1a local.
- Email opcional en LDAP: se genera un fallback username@<dominio>.
"""

import logging

from django.conf import settings
from django_auth_ldap.backend import LDAPBackend

logger = logging.getLogger(__name__)


class AuraLDAPBackend(LDAPBackend):
    """
    Backend LDAP personalizado para el esquema auth_user de Aura.

    El flujo normal de LDAPBackend llama a get_or_build_user() para
    obtener o crear el objeto User local. Esta implementación usa el
    CustomUserManager que maneja el bootstrap de created_by.
    """

    def get_or_build_user(self, username, ldap_user):
        """
        Crea o recupera el usuario local correspondiente al entry LDAP.

        Returns:
            (User, built: bool)
        """
        from apps.accounts.models import User

        # Usuario existente no eliminado → reutilizar sin crear uno nuevo
        try:
            user = User.objects.get(username=username, deleted_at__isnull=True)
            return user, False
        except User.DoesNotExist:
            pass

        # --- Leer atributos del entry LDAP ---

        # Email: leer del atributo configurado; fallback a username@dominio
        mail_attr  = getattr(settings, 'LDAP_ATTR_MAIL', 'mail')
        domain     = getattr(settings, 'LDAP_EMAIL_FALLBACK_DOMAIN', 'ldap.local')
        email_list = ldap_user.attrs.get(mail_attr, [])
        if email_list:
            email = email_list[0]
        else:
            email = f'{username}@{domain}'
            logger.warning(
                "LDAP user '%s' has no '%s' attribute. Using generated email: %s",
                username, mail_attr, email,
            )

        # Nombre de display
        name_attr = getattr(settings, 'LDAP_ATTR_DISPLAY_NAME', 'displayName')
        name_list = ldap_user.attrs.get(name_attr, [])
        name = name_list[0] if name_list else username

        # --- Crear usuario ---
        # password=None → CustomUserManager llama a make_password(None)
        # que produce un hash con prefijo '!' (nunca válido para login local).
        # El campo password NOT NULL queda satisfecho.
        user = User.objects.create_user(
            username=username,
            email=email,
            password=None,
        )
        user.name = name
        user.save(update_fields=['name', 'updated_at'])



        logger.info(
            "Created local user from LDAP: username=%s email=%s",
            username, email,
        )
        return user, True

