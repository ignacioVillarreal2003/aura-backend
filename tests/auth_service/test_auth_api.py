"""
Tests funcionales del Auth Service.

Casos de prueba cubiertos (según documentación de casos de prueba):

  RF-U001 / RF-A001 — Inicio de Sesión:
    TC01  Credenciales válidas → 200 + tokens                 (RF-U001-TC02, RF-A001-TC01)
    TC02  Credenciales inválidas → 401                        (RF-U001-TC04, RF-A001-TC02)
    TC03  Cuenta bloqueada/inactiva → 401                     (RF-U001-TC05)
    TC04  Error de sistema → 500                              (RF-U001-TC06, RF-A001-TC03)
    TC05  Campos faltantes → 400

  Refresh Token:
    TC01  Token válido → 200 + nuevos tokens
    TC02  Token inválido/expirado → 401
    TC03  Formato UUID inválido → 400

  RF-U007 / RF-A023 — Cerrar Sesión:
    TC01  Token válido → 200 + confirmación                   (RF-U007-TC01, RF-A023-TC01)
    TC02  Token inválido → 401                                (RF-U007-TC03, RF-A023-TC03)
    TC03  Campo faltante → 400

  Validate Token:
    TC01  Bearer válido → 200 + datos usuario
    TC02  Header ausente → 401
    TC03  Formato de header inválido → 401
    TC04  Token inválido/expirado → 401
"""

from conftest import make_user, TOKEN_RESPONSE, VALID_REFRESH_TOKEN, VALID_ACCESS_TOKEN, USER_INFO


# ===========================================================================
# POST /auth/login
# ===========================================================================

class TestLogin:

    # RF-U001-TC02 / RF-A001-TC01 — Login exitoso
    def test_login_credenciales_validas_retorna_200_y_tokens(self, client, mock_auth_service):
        mock_auth_service["authenticate_user"].return_value = make_user()
        mock_auth_service["issue_tokens_for_user"].return_value = TOKEN_RESPONSE

        response = client.post("/auth/login", data={"username": "testuser", "password": "pass123"}, format="json")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"
        mock_auth_service["issue_tokens_for_user"].assert_called_once()

    # RF-U001-TC04 / RF-A001-TC02 — Credenciales incorrectas
    def test_login_credenciales_invalidas_retorna_401(self, client, mock_auth_service):
        mock_auth_service["authenticate_user"].return_value = None

        response = client.post("/auth/login", data={"username": "noexiste", "password": "mal"}, format="json")

        assert response.status_code == 401
        assert "detail" in response.json()
        mock_auth_service["issue_tokens_for_user"].assert_not_called()

    # RF-U001-TC05 — Cuenta bloqueada o inactiva
    def test_login_cuenta_bloqueada_retorna_401(self, client, mock_auth_service):
        # authenticate_user devuelve None tanto para credenciales inválidas como para cuenta bloqueada
        mock_auth_service["authenticate_user"].return_value = None

        response = client.post("/auth/login", data={"username": "bloqueado", "password": "pass"}, format="json")

        assert response.status_code == 401
        assert "detail" in response.json()

    # RF-U001-TC06 / RF-A001-TC03 — Error de sistema
    def test_login_error_sistema_retorna_500(self, client, mock_auth_service):
        mock_auth_service["authenticate_user"].side_effect = Exception("DB unreachable")

        response = client.post("/auth/login", data={"username": "testuser", "password": "pass"}, format="json")

        assert response.status_code == 500

    # Campo password faltante → 400
    def test_login_campo_password_faltante_retorna_400(self, client, mock_auth_service):
        response = client.post("/auth/login", data={"username": "testuser"}, format="json")

        assert response.status_code == 400
        mock_auth_service["authenticate_user"].assert_not_called()

    # Campos completamente vacíos → 400
    def test_login_sin_campos_retorna_400(self, client, mock_auth_service):
        response = client.post("/auth/login", data={}, format="json")

        assert response.status_code == 400
        mock_auth_service["authenticate_user"].assert_not_called()


# ===========================================================================
# POST /auth/refresh
# ===========================================================================

class TestRefreshToken:

    # Token válido → 200 + nuevos tokens
    def test_refresh_token_valido_retorna_200_y_nuevos_tokens(self, client, mock_auth_service):
        mock_auth_service["rotate_refresh_token"].return_value = TOKEN_RESPONSE

        response = client.post(
            "/auth/refresh",
            data={"refresh_token": VALID_REFRESH_TOKEN},
            format="json",
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"

    # Token inválido o revocado → 401
    def test_refresh_token_invalido_retorna_401(self, client, mock_auth_service):
        mock_auth_service["rotate_refresh_token"].return_value = None

        response = client.post(
            "/auth/refresh",
            data={"refresh_token": "00000000-0000-0000-0000-000000000000"},
            format="json",
        )

        assert response.status_code == 401
        assert "detail" in response.json()

    # Formato no UUID → 400 (validación del serializer)
    def test_refresh_token_formato_invalido_retorna_400(self, client, mock_auth_service):
        response = client.post(
            "/auth/refresh",
            data={"refresh_token": "no-es-un-uuid-valido"},
            format="json",
        )

        assert response.status_code == 400
        mock_auth_service["rotate_refresh_token"].assert_not_called()


# ===========================================================================
# POST /auth/logout
# ===========================================================================

class TestLogout:

    # RF-U007-TC01 / RF-A023-TC01 — Cierre de sesión exitoso
    def test_logout_token_valido_retorna_200(self, client, mock_auth_service):
        mock_auth_service["revoke_refresh_token"].return_value = True

        response = client.post(
            "/auth/logout",
            data={"refresh_token": VALID_REFRESH_TOKEN},
            format="json",
        )

        assert response.status_code == 200
        assert response.json()["detail"] == "Logged out."

    # RF-U007-TC03 / RF-A023-TC03 — Token inválido o ya revocado
    def test_logout_token_invalido_retorna_401(self, client, mock_auth_service):
        mock_auth_service["revoke_refresh_token"].return_value = False

        response = client.post(
            "/auth/logout",
            data={"refresh_token": "00000000-0000-0000-0000-000000000000"},
            format="json",
        )

        assert response.status_code == 401
        assert "detail" in response.json()

    # Campo faltante → 400
    def test_logout_campo_faltante_retorna_400(self, client, mock_auth_service):
        response = client.post("/auth/logout", data={}, format="json")

        assert response.status_code == 400
        mock_auth_service["revoke_refresh_token"].assert_not_called()


# ===========================================================================
# GET /auth/validate
# ===========================================================================

class TestValidateToken:

    # Bearer válido → 200 + datos del usuario
    def test_validate_bearer_valido_retorna_200_y_datos_usuario(self, client, mock_auth_service):
        mock_auth_service["get_user_info"].return_value = USER_INFO

        response = client.get("/auth/validate", HTTP_AUTHORIZATION=f"Bearer {VALID_ACCESS_TOKEN}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == USER_INFO["id"]
        assert data["email"] == USER_INFO["email"]
        assert data["username"] == USER_INFO["username"]
        assert "roles" in data
        assert "permissions" in data

    # Sin header Authorization → 401
    def test_validate_sin_header_retorna_401(self, client, mock_auth_service):
        response = client.get("/auth/validate")

        assert response.status_code == 401
        mock_auth_service["get_user_info"].assert_not_called()

    # Header sin prefijo "Bearer" → 401
    def test_validate_header_formato_invalido_retorna_401(self, client, mock_auth_service):
        response = client.get("/auth/validate", HTTP_AUTHORIZATION="Token no-bearer-prefix")

        assert response.status_code == 401
        mock_auth_service["get_user_info"].assert_not_called()

    # Token inválido o expirado → 401
    def test_validate_token_invalido_retorna_401(self, client, mock_auth_service):
        mock_auth_service["get_user_info"].return_value = None

        response = client.get("/auth/validate", HTTP_AUTHORIZATION="Bearer token.invalido.aqui")

        assert response.status_code == 401
        assert "detail" in response.json()
