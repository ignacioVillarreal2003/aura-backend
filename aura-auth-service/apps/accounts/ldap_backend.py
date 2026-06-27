"""Backend LDAP adaptado al esquema auth_user de Aura."""

import logging

from django.conf import settings
from django_auth_ldap.backend import LDAPBackend

logger = logging.getLogger(__name__)


class AuraLDAPBackend(LDAPBackend):
    """Backend LDAP a medida para el esquema auth_user de Aura."""

    def get_or_build_user(self, username, ldap_user):
        """Crea o recupera el usuario local del entry LDAP."""
        from apps.accounts.models import User

        try:
            user = User.objects.get(username=username, deleted_at__isnull=True)
            return user, False
        except User.DoesNotExist:
            pass

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

        name_attr = getattr(settings, 'LDAP_ATTR_DISPLAY_NAME', 'displayName')
        name_list = ldap_user.attrs.get(name_attr, [])
        name = name_list[0] if name_list else username

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

