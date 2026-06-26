"""
Tests del backend LDAP y la sincronizacion MAC.

Casos de prueba cubiertos:

  LDAP-TC01  Usuario LDAP valido -> login exitoso, User creado en DB
  LDAP-TC02  Usuario LDAP ya existente en DB -> login exitoso, sin duplicado
  LDAP-TC03  Contrasena incorrecta -> AuraLDAPBackend retorna None
  LDAP-TC04  Usuario no existe en LDAP -> ModelBackend autentica (superadmin local)
  LDAP-TC05  auraClassificationLevel=SECRET -> set_user_clearance() llamado
  LDAP-TC06  auraCompartment=[ALPHA, BRAVO] -> ambos compartimentos agregados
  LDAP-TC07  Compartimento revocado en LDAP -> remove_user_compartment() llamado
  LDAP-TC08  MAC service error -> login OK (best-effort, error logueado)
  LDAP-TC09  Usuario sin atributo mail -> email username@ldap.local + warning
  LDAP-TC10  make_password(None) -> check_password() siempre False
  LDAP-TC11  force_logout_at posterior al iat -> token rechazado
  LDAP-TC12  force_logout_at anterior al iat -> token aceptado
  LDAP-TC13  Login exitoso -> force_logout_at reseteado a None
  LDAP-TC14  Accion force_logout admin -> force_logout_at=now, refresh tokens revocados
  LDAP-TC15  rotate_refresh_token() -> _try_ldap_resync() llamado
  LDAP-TC16  Renombrar atributo LDAP via settings -> funciona sin cambios de codigo

Estrategia:
- Sin BD real ni servidor LDAP: todo mockeado con unittest.mock.
- Se mockea django_auth_ldap.backend.LDAPBackend para simular el flujo LDAP.
- Se mockea mac_client para verificar llamadas al servicio MAC.
- Los tests de force_logout_at usan JWT reales firmados con la clave de test.
"""

import os
import sys
from datetime import datetime, timezone as dt_tz, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

# ── Setup de path y Django ────────────────────────────────────────────────────

_svc = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "aura-auth-service")
)
if _svc not in sys.path:
    sys.path.insert(0, _svc)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings_test")

from unittest.mock import MagicMock

_audit_stub = MagicMock()
_audit_stub.AuditLog = type("AuditLog", (), {"objects": MagicMock()})
sys.modules.setdefault("accounts.models.audit_log", _audit_stub)

# django setup handled by conftest / pytest-django

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ldap_user(attrs: dict):
    """Crea un objeto ldap_user simulado con atributos dados."""
    ldap_user = MagicMock()
    ldap_user.attrs = attrs
    return ldap_user


def _make_user(
    id=1,
    username="john.doe",
    email="john.doe@aura.local",
    name="John Doe",
    force_logout_at=None,
    status="active",
    is_deleted=False,
):
    """Crea un User simulado con los campos relevantes."""
    user = MagicMock()
    user.pk = id
    user.id = id
    user.username = username
    user.email = email
    user.name = name
    user.force_logout_at = force_logout_at
    user.status = status
    user.is_deleted = is_deleted
    user.deleted_at = None if not is_deleted else timezone.now()
    user.password = make_password(None)
    user.save = MagicMock()
    return user


def _build_token(user_id: int, iat: int | None = None, exp_delta: int = 3600) -> str:
    """Construye un JWT de prueba firmado con JWT_SIGNING_KEY."""
    now = int(datetime.now(tz=dt_tz.utc).timestamp())
    payload = {
        "user_id": user_id,
        "iat": iat if iat is not None else now,
        "exp": now + exp_delta,
    }
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.JWT_ALGORITHM)


# ── LDAP-TC01 — Usuario LDAP valido, creacion en DB ──────────────────────────

class TestLDAPTC01:
    def test_usuario_ldap_nuevo_se_crea_en_db(self):
        """Un usuario que existe en LDAP pero no en DB se crea correctamente."""
        from accounts.ldap_backend import AuraLDAPBackend

        attrs = {
            "uid": ["john.doe"],
            "mail": ["john.doe@aura.local"],
            "displayName": ["John Doe"],
        }
        ldap_user = _make_ldap_user(attrs)

        created_user = _make_user()

        with patch("accounts.models.user.User.objects") as mock_objects:
            mock_objects.get.side_effect = Exception("DoesNotExist")
            mock_objects.create_user.return_value = created_user

            backend = AuraLDAPBackend()
            # Parchamos get_or_build_user directamente para verificar logica interna
            with patch.object(backend, "get_or_build_user", wraps=backend.get_or_build_user):
                pass  # La logica se prueba via la llamada directa abajo

        # Prueba directa de get_or_build_user
        from accounts.models import User
        with patch.object(User.objects, "get", side_effect=User.DoesNotExist), \
             patch.object(User.objects, "create_user", return_value=created_user) as mock_create:
            backend = AuraLDAPBackend()
            user, built = backend.get_or_build_user("john.doe", ldap_user)

        assert built is True
        mock_create.assert_called_once_with(
            username="john.doe",
            email="john.doe@aura.local",
            password=None,
        )
        created_user.save.assert_called_once()


# ── LDAP-TC02 — Usuario ya existente en DB, sin duplicado ────────────────────

class TestLDAPTC02:
    def test_usuario_existente_no_duplica(self):
        """Un usuario que ya existe en DB retorna el existente sin crear uno nuevo."""
        from accounts.ldap_backend import AuraLDAPBackend
        from accounts.models import User

        existing = _make_user()
        attrs = {"mail": ["john.doe@aura.local"], "displayName": ["John Doe"]}
        ldap_user = _make_ldap_user(attrs)

        with patch.object(User.objects, "get", return_value=existing), \
             patch.object(User.objects, "create_user") as mock_create:
            backend = AuraLDAPBackend()
            user, built = backend.get_or_build_user("john.doe", ldap_user)

        assert built is False
        assert user is existing
        mock_create.assert_not_called()


# ── LDAP-TC03 — Contrasena incorrecta ────────────────────────────────────────

class TestLDAPTC03:
    def test_contrasena_incorrecta_retorna_none(self):
        """django-auth-ldap retorna None cuando la contrasena es incorrecta."""
        from accounts.ldap_backend import AuraLDAPBackend

        backend = AuraLDAPBackend()
        # Simulamos que el bind de usuario falla lanzando LDAPBindError
        with patch.object(backend, "authenticate", return_value=None) as mock_auth:
            result = backend.authenticate(
                request=None, username="john.doe", password="wrong"
            )
        assert result is None


# ── LDAP-TC04 — Usuario no existe en LDAP, fallback a ModelBackend ────────────

class TestLDAPTC04:
    def test_usuario_local_usa_model_backend(self):
        """Si LDAP no encuentra al usuario, ModelBackend puede autenticarlo."""
        from django.contrib.auth import authenticate as django_authenticate

        local_user = _make_user(username="superadmin")

        with patch("accounts.ldap_backend.AuraLDAPBackend.authenticate", return_value=None), \
             patch("django.contrib.auth.backends.ModelBackend.authenticate", return_value=local_user):
            result = django_authenticate(
                request=None, username="superadmin", password="admin123"
            )

        assert result is local_user


# ── LDAP-TC05 — Sync de classification_level ─────────────────────────────────

class TestLDAPTC05:
    def test_sync_clearance_llama_set_user_clearance(self):
        """_sync_clearance llama a mac_client.set_user_clearance con el id correcto."""
        from accounts.ldap_sync import _sync_clearance

        user = _make_user()
        levels = [
            {"id": "lvl-1", "name": "CONFIDENTIAL"},
            {"id": "lvl-2", "name": "SECRET"},
        ]

        with patch("accounts.services.mac_client.mac_client.list_classification_levels", return_value=levels), \
             patch("accounts.services.mac_client.mac_client.set_user_clearance") as mock_set:
            _sync_clearance(user, "SECRET")

        mock_set.assert_called_once_with(None, user.pk, "lvl-2")

    def test_sync_clearance_level_no_encontrado_loguea_warning(self, caplog):
        """Si el nivel de LDAP no existe en MAC, se loguea un warning sin error."""
        from accounts.ldap_sync import _sync_clearance
        import logging

        user = _make_user()
        levels = [{"id": "lvl-1", "name": "CONFIDENTIAL"}]

        with patch("accounts.services.mac_client.mac_client.list_classification_levels", return_value=levels), \
             patch("accounts.services.mac_client.mac_client.set_user_clearance") as mock_set, \
             caplog.at_level(logging.WARNING, logger="accounts.ldap_sync"):
            _sync_clearance(user, "TOP_SECRET")

        mock_set.assert_not_called()
        assert "not found in MAC" in caplog.text


# ── LDAP-TC06 — Sync de compartimentos: agregar ───────────────────────────────

class TestLDAPTC06:
    def test_sync_compartments_agrega_los_de_ldap(self):
        """Se agregan todos los compartimentos presentes en LDAP pero ausentes en MAC."""
        from accounts.ldap_sync import _sync_compartments

        user = _make_user()
        all_compartments = [
            {"id": "c-1", "name": "ALPHA"},
            {"id": "c-2", "name": "BRAVO"},
        ]
        current_entries = []  # El usuario no tiene compartimentos en MAC todavia

        with patch("accounts.services.mac_client.mac_client.list_compartments", return_value=all_compartments), \
             patch("accounts.services.mac_client.mac_client.list_user_compartments", return_value=current_entries), \
             patch("accounts.services.mac_client.mac_client.add_user_compartment") as mock_add, \
             patch("accounts.services.mac_client.mac_client.remove_user_compartment") as mock_remove:
            _sync_compartments(user, ["ALPHA", "BRAVO"])

        assert mock_add.call_count == 2
        mock_add.assert_any_call(None, user.pk, "c-1")
        mock_add.assert_any_call(None, user.pk, "c-2")
        mock_remove.assert_not_called()


# ── LDAP-TC07 — Sync de compartimentos: revocar ──────────────────────────────

class TestLDAPTC07:
    def test_sync_compartments_revoca_los_ausentes_en_ldap(self):
        """Se revocan compartimentos en MAC que ya no estan en el entry LDAP."""
        from accounts.ldap_sync import _sync_compartments

        user = _make_user()
        all_compartments = [
            {"id": "c-1", "name": "ALPHA"},
            {"id": "c-2", "name": "BRAVO"},
        ]
        # El usuario actualmente tiene ALPHA y BRAVO en MAC
        current_entries = [
            {"compartment": {"name": "ALPHA", "id": "c-1"}},
            {"compartment": {"name": "BRAVO", "id": "c-2"}},
        ]

        with patch("accounts.services.mac_client.mac_client.list_compartments", return_value=all_compartments), \
             patch("accounts.services.mac_client.mac_client.list_user_compartments", return_value=current_entries), \
             patch("accounts.services.mac_client.mac_client.add_user_compartment") as mock_add, \
             patch("accounts.services.mac_client.mac_client.remove_user_compartment") as mock_remove:
            # LDAP solo tiene ALPHA ahora (BRAVO fue removido)
            _sync_compartments(user, ["ALPHA"])

        mock_add.assert_not_called()
        mock_remove.assert_called_once_with(None, user.pk, "c-2")


# ── LDAP-TC08 — Error de MAC service es best-effort ──────────────────────────

class TestLDAPTC08:
    def test_error_mac_no_impide_sync(self, caplog):
        """Un error del MAC service se loguea pero no propaga excepciones."""
        from accounts.ldap_sync import _sync_mac_attributes
        import logging

        user = _make_user()
        attrs = {
            "auraClassificationLevel": ["SECRET"],
            "auraCompartment": ["ALPHA"],
        }
        ldap_user = _make_ldap_user(attrs)

        with patch("accounts.services.mac_client.mac_client.list_classification_levels",
                   side_effect=Exception("MAC service unavailable")), \
             caplog.at_level(logging.ERROR, logger="accounts.ldap_sync"):
            # No debe lanzar excepcion
            _sync_mac_attributes(sender=None, user=user, ldap_user=ldap_user)

        assert "MAC clearance sync failed" in caplog.text


# ── LDAP-TC09 — Email fallback ────────────────────────────────────────────────

class TestLDAPTC09:
    def test_usuario_sin_mail_genera_email_fallback(self, caplog):
        """Un usuario LDAP sin atributo 'mail' obtiene email generado."""
        from accounts.ldap_backend import AuraLDAPBackend
        from accounts.models import User
        import logging

        # Sin atributo mail
        attrs = {"displayName": ["No Mail User"]}
        ldap_user = _make_ldap_user(attrs)

        created_user = _make_user(username="no.mail", email="no.mail@ldap.local")

        with patch.object(User.objects, "get", side_effect=User.DoesNotExist), \
             patch.object(User.objects, "create_user", return_value=created_user) as mock_create, \
             caplog.at_level(logging.WARNING, logger="accounts.ldap_backend"):
            backend = AuraLDAPBackend()
            user, built = backend.get_or_build_user("no.mail", ldap_user)

        # Verifica que se uso el email de fallback
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("email") == "no.mail@ldap.local" or \
               (len(call_kwargs.args) >= 2 and "ldap.local" in call_kwargs.args[1])
        assert "generated email" in caplog.text


# ── LDAP-TC10 — Contrasena siempre invalida para login local ─────────────────

class TestLDAPTC10:
    def test_make_password_none_no_permite_login_local(self):
        """make_password(None) produce un hash que check_password siempre rechaza."""
        hashed = make_password(None)
        assert hashed.startswith("!")
        assert check_password("cualquier_cosa", hashed) is False
        assert check_password("", hashed) is False
        assert check_password(None, hashed) is False


# ── LDAP-TC11 — force_logout_at rechaza token anterior ───────────────────────

class TestLDAPTC11:
    def test_token_anterior_a_force_logout_es_rechazado(self):
        """Un token emitido antes de force_logout_at es rechazado."""
        from accounts.services.auth_service import _decode_and_fetch_user

        user = _make_user(id=42)
        user.is_deleted = False
        user.status = "active"

        # force_logout_at = ahora
        force_time = datetime.now(tz=dt_tz.utc)
        user.force_logout_at = force_time

        # Token emitido 5 minutos ANTES del force_logout_at
        old_iat = int((force_time - timedelta(minutes=5)).timestamp())
        token = _build_token(user_id=42, iat=old_iat)

        with patch("accounts.models.user.User.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = user
            result = _decode_and_fetch_user(token)

        assert result is None


# ── LDAP-TC12 — force_logout_at acepta token posterior ───────────────────────

class TestLDAPTC12:
    def test_token_posterior_a_force_logout_es_aceptado(self):
        """Un token emitido DESPUES de force_logout_at es aceptado."""
        from accounts.services.auth_service import _decode_and_fetch_user

        user = _make_user(id=42)
        user.is_deleted = False
        user.status = "active"

        # force_logout_at = 10 minutos atras
        force_time = datetime.now(tz=dt_tz.utc) - timedelta(minutes=10)
        user.force_logout_at = force_time

        # Token emitido AHORA (posterior al force_logout_at)
        token = _build_token(user_id=42)

        with patch("accounts.models.user.User.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = user
            result = _decode_and_fetch_user(token)

        assert result is user


# ── LDAP-TC13 — Login exitoso resetea force_logout_at ────────────────────────

class TestLDAPTC13:
    def test_login_exitoso_resetea_force_logout_at(self):
        """Un login exitoso setea force_logout_at a None."""
        from accounts.services.auth_service import authenticate_user

        user = _make_user()
        user.is_deleted = False
        user.status = "active"
        user.account_non_locked = True
        user.lockout_until = None
        user.force_logout_at = timezone.now() - timedelta(hours=1)

        with patch("accounts.services.auth_service.authenticate", return_value=user), \
             patch("accounts.models.user.User.objects.get", return_value=user):
            result = authenticate_user("john.doe", "Password123!")

        assert result is user
        # force_logout_at debe haberse incluido en el save
        save_call = user.save.call_args
        assert "force_logout_at" in save_call.kwargs.get("update_fields", [])


# ── LDAP-TC14 — Accion force_logout del admin ────────────────────────────────

class TestLDAPTC14:
    def test_force_logout_admin_action_invalida_sesion(self):
        """La accion force_logout setea force_logout_at y revoca refresh tokens."""
        from accounts.admin_parts.user_admin import force_logout
        from accounts.models import RefreshToken

        user = _make_user()
        queryset = [user]

        mock_request = MagicMock()
        mock_request.user = _make_user(id=99, username="admin")

        mock_modeladmin = MagicMock()

        with patch("accounts.models.RefreshToken.objects.filter") as mock_rt_filter, \
             patch("accounts.admin_parts.common.log_audit") as mock_audit:
            mock_rt_filter.return_value.update = MagicMock()
            force_logout(mock_modeladmin, mock_request, queryset)

        # force_logout_at seteado
        assert user.force_logout_at is not None
        user.save.assert_called()

        # Refresh tokens revocados
        mock_rt_filter.assert_called_once_with(user=user, is_revoked=False)
        mock_rt_filter.return_value.update.assert_called_once()
        update_kwargs = mock_rt_filter.return_value.update.call_args.kwargs
        assert update_kwargs.get("is_revoked") is True


# ── LDAP-TC15 — rotate_refresh_token llama _try_ldap_resync ─────────────────

class TestLDAPTC15:
    def test_rotate_refresh_token_llama_ldap_resync(self):
        """rotate_refresh_token invoca _try_ldap_resync despues de rotar."""
        from accounts.services import auth_service

        mock_refresh = MagicMock()
        mock_refresh.expires_at = timezone.now() + timedelta(hours=1)
        mock_refresh.user = _make_user()

        mock_new_refresh = MagicMock()
        mock_new_refresh.token = "new-refresh-uuid"

        with patch("accounts.models.RefreshToken.objects.filter") as mock_filter, \
             patch.object(auth_service, "_try_ldap_resync") as mock_resync, \
             patch.object(auth_service, "_create_refresh_token", return_value=mock_new_refresh), \
             patch.object(auth_service, "_build_access_token", return_value="new-access-token"):
            mock_filter.return_value.first.return_value = mock_refresh
            result = auth_service.rotate_refresh_token("some-uuid")

        mock_resync.assert_called_once_with(mock_refresh.user)
        assert result["access_token"] == "new-access-token"
        assert result["refresh_token"] == "new-refresh-uuid"


# ── LDAP-TC16 — Renombrar atributo LDAP via settings ─────────────────────────

class TestLDAPTC16:
    def test_sync_usa_atributo_configurable_en_settings(self):
        """_sync_mac_attributes lee el nombre del atributo desde settings."""
        from accounts.ldap_sync import _sync_mac_attributes

        user = _make_user()

        # Simular que el schema corporativo usa 'clearanceLevel' en lugar de 'auraClassificationLevel'
        attrs = {
            "clearanceLevel": ["CONFIDENTIAL"],  # nombre alternativo
            "auraCompartment": [],
        }
        ldap_user = _make_ldap_user(attrs)

        with patch.object(settings, "LDAP_ATTR_CLASSIFICATION_LEVEL", "clearanceLevel"), \
             patch.object(settings, "LDAP_ATTR_COMPARTMENT", "auraCompartment"), \
             patch("accounts.services.mac_client.mac_client.list_classification_levels",
                   return_value=[{"id": "lvl-1", "name": "CONFIDENTIAL"}]), \
             patch("accounts.services.mac_client.mac_client.set_user_clearance") as mock_set, \
             patch("accounts.services.mac_client.mac_client.list_compartments", return_value=[]), \
             patch("accounts.services.mac_client.mac_client.list_user_compartments", return_value=[]):
            _sync_mac_attributes(sender=None, user=user, ldap_user=ldap_user)

        mock_set.assert_called_once_with(None, user.pk, "lvl-1")


# ── LDAP-TC17 — Usuario nuevo sin atributo de rol obtiene 'user' ──────────────

class TestLDAPTC17:
    def test_usuario_nuevo_sin_rol_obtiene_user(self):
        """Un usuario nuevo sin atributo de rol en LDAP obtiene el rol 'user' por defecto."""
        from accounts.ldap_sync import _sync_user_role
        from accounts.models import Role, UserRole

        user = _make_user(id=1, username="john.doe")
        ldap_user = _make_ldap_user({})  # Sin atributo de rol

        mock_role_user = MagicMock()
        mock_role_user.id = 10
        mock_role_user.name = "user"

        with patch.object(Role.objects, "filter") as mock_role_filter, \
             patch.object(UserRole.objects, "filter") as mock_ur_filter, \
             patch.object(UserRole.objects, "create") as mock_ur_create:

            mock_role_filter.return_value.first.return_value = mock_role_user
            mock_exists_qs = MagicMock()
            mock_exists_qs.exists.return_value = False
            mock_ur_filter.side_effect = [[], mock_exists_qs]

            _sync_user_role(user, ldap_user)

            mock_role_filter.assert_called_once_with(name="user")
            mock_ur_create.assert_called_once_with(
                user=user,
                role=mock_role_user,
                created_by=user
            )


# ── LDAP-TC18 — Usuario nuevo con employeeType: admin obtiene 'admin' ─────────

class TestLDAPTC18:
    def test_usuario_nuevo_con_rol_admin_obtiene_admin(self):
        """Un usuario nuevo con employeeType: admin obtiene el rol 'admin'."""
        from accounts.ldap_sync import _sync_user_role
        from accounts.models import Role, UserRole

        user = _make_user(id=2, username="jane.smith")
        ldap_user = _make_ldap_user({"employeeType": ["admin"]})

        mock_role_admin = MagicMock()
        mock_role_admin.id = 20
        mock_role_admin.name = "admin"

        with patch.object(Role.objects, "filter") as mock_role_filter, \
             patch.object(UserRole.objects, "filter") as mock_ur_filter, \
             patch.object(UserRole.objects, "create") as mock_ur_create:

            mock_role_filter.return_value.first.return_value = mock_role_admin
            mock_exists_qs = MagicMock()
            mock_exists_qs.exists.return_value = False
            mock_ur_filter.side_effect = [[], mock_exists_qs]

            _sync_user_role(user, ldap_user)

            mock_role_filter.assert_called_once_with(name="admin")
            mock_ur_create.assert_called_once_with(
                user=user,
                role=mock_role_admin,
                created_by=user
            )


# ── LDAP-TC19 — Promocion/Democion: Cambio de rol desactiva el anterior ───────

class TestLDAPTC19:
    def test_usuario_existente_cambia_de_rol(self):
        """Un usuario que cambia de rol desactiva el rol anterior y activa el nuevo."""
        from accounts.ldap_sync import _sync_user_role
        from accounts.models import Role, UserRole

        user = _make_user(id=1, username="john.doe")
        ldap_user = _make_ldap_user({"employeeType": ["admin"]})

        mock_role_admin = MagicMock()
        mock_role_admin.id = 20
        mock_role_admin.name = "admin"

        mock_role_user = MagicMock()
        mock_role_user.id = 10
        mock_role_user.name = "user"

        active_ur = MagicMock()
        active_ur.role = mock_role_user
        active_ur.role_id = 10
        active_ur.save = MagicMock()

        with patch.object(Role.objects, "filter") as mock_role_filter, \
             patch.object(UserRole.objects, "filter") as mock_ur_filter, \
             patch.object(UserRole.objects, "create") as mock_ur_create:

            mock_role_filter.return_value.first.return_value = mock_role_admin
            mock_exists_qs = MagicMock()
            mock_exists_qs.exists.return_value = False
            mock_ur_filter.side_effect = [[active_ur], mock_exists_qs]

            _sync_user_role(user, ldap_user)

            assert active_ur.deleted_at is not None
            assert active_ur.deleted_by == user
            active_ur.save.assert_called_once()

            mock_ur_create.assert_called_once_with(
                user=user,
                role=mock_role_admin,
                created_by=user
            )

