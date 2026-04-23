"""
Tests funcionales del Chat Service — gestión de chats (individuales y grupales).

Casos de prueba cubiertos (según documentación de casos de prueba):
  Chats Individuales:
    RF-UI005-TC01  Crear nuevo chat individual
    RF-UI005-TC02  Crear chat - Error sistema
    RF-UI006-TC01  Lista de chats individuales
    RF-UI006-TC02  Lista de chats - Error sistema
    RF-UI007-TC01  Seleccionar chat (obtener por ID)
    RF-UI007-TC03  Seleccionar chat - Error abrir (no encontrado)
    RF-UI001-TC01  Personalización de chat individual (actualizar)
    RF-UI001-TC03  Personalización - Error guardar
    RF-UI003-TC01  Eliminación de chat individual
    RF-UI003-TC03  Eliminación - Error sistema
    Autorización    Acceso denegado a chat ajeno (403)

  Chats Grupales:
    RF-UG002-TC01  Crear grupo
    RF-UG002-TC02  Crear grupo - Datos incompletos (nombre faltante)
    RF-UG002-TC03  Crear grupo - Error sistema
    RF-UG003-TC01  Acceso a grupos (listar)
"""

from app.application.exceptions.api_exceptions import (
    ForbiddenError,
    NotFoundError,
)

from conftest import make_chat_list_response, make_chat_response


# ===========================================================================
# POST /api/v1/chats — Crear chat
# ===========================================================================

class TestCrearChat:
    # RF-UI005-TC01
    def test_crear_chat_individual_exitoso(self, client, mock_chat_service):
        """Sistema crea el chat, lo agrega a la lista y retorna 201."""
        mock_chat_service.create_chat.return_value = make_chat_response(name="Mi Chat")

        response = client.post(
            "/api/v1/chats",
            json={"name": "Mi Chat", "member_ids": []},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Mi Chat"
        assert data["chat_type"] == "individual"
        assert data["id"] == 1

    # RF-UI005-TC02
    def test_crear_chat_error_sistema(self, client, mock_chat_service):
        """Cuando ocurre un fallo interno el sistema devuelve 500."""
        mock_chat_service.create_chat.side_effect = Exception("DB connection lost")

        response = client.post(
            "/api/v1/chats",
            json={"name": "Mi Chat", "member_ids": []},
        )

        assert response.status_code == 500

    def test_crear_chat_nombre_vacio_retorna_422(self, client, mock_chat_service):
        """El nombre es obligatorio; sin él FastAPI devuelve 422."""
        response = client.post(
            "/api/v1/chats",
            json={"member_ids": []},
        )

        assert response.status_code == 422

    # RF-UG002-TC01
    def test_crear_grupo_con_miembros(self, client, mock_chat_service):
        """Sistema crea el grupo, asocia al usuario como admin y lo muestra en la lista."""
        mock_chat_service.create_chat.return_value = make_chat_response(
            name="Grupo Dev", chat_type="group"
        )

        response = client.post(
            "/api/v1/chats",
            json={"name": "Grupo Dev", "member_ids": [2, 3]},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Grupo Dev"
        assert data["chat_type"] == "group"

    # RF-UG002-TC02
    def test_crear_grupo_sin_nombre_retorna_422(self, client, mock_chat_service):
        """Sin nombre obligatorio el sistema devuelve error de validación 422."""
        response = client.post(
            "/api/v1/chats",
            json={"member_ids": [2, 3]},
        )

        assert response.status_code == 422

    # RF-UG002-TC03
    def test_crear_grupo_error_sistema(self, client, mock_chat_service):
        """Confirmación con fallo de sistema devuelve 500."""
        mock_chat_service.create_chat.side_effect = Exception("RabbitMQ unavailable")

        response = client.post(
            "/api/v1/chats",
            json={"name": "Grupo Roto", "member_ids": [2]},
        )

        assert response.status_code == 500


# ===========================================================================
# GET /api/v1/chats — Listar chats
# ===========================================================================

class TestListarChats:
    # RF-UI006-TC01 / RF-UG003-TC01
    def test_listar_chats_exitoso(self, client, mock_chat_service):
        """Sistema muestra la lista de chats del usuario."""
        mock_chat_service.list_chats.return_value = make_chat_list_response()

        response = client.get("/api/v1/chats")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Chat de prueba"

    # RF-UI006-TC02
    def test_listar_chats_error_sistema(self, client, mock_chat_service):
        """Acceder a historial con fallo de sistema devuelve 500."""
        mock_chat_service.list_chats.side_effect = Exception("DB unavailable")

        response = client.get("/api/v1/chats")

        assert response.status_code == 500

    def test_listar_chats_lista_vacia(self, client, mock_chat_service):
        """Cuando el usuario no tiene chats la lista retorna vacía con 200."""
        mock_chat_service.list_chats.return_value = make_chat_list_response(chats=[])

        response = client.get("/api/v1/chats")

        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_listar_chats_con_limite(self, client, mock_chat_service):
        """El parámetro limit es aceptado correctamente."""
        mock_chat_service.list_chats.return_value = make_chat_list_response()

        response = client.get("/api/v1/chats?limit=5")

        assert response.status_code == 200

    def test_listar_chats_limite_invalido_retorna_422(self, client, mock_chat_service):
        """limit=0 viola la restricción ge=1 y devuelve 422."""
        response = client.get("/api/v1/chats?limit=0")

        assert response.status_code == 422


# ===========================================================================
# GET /api/v1/chats/{chat_id} — Obtener chat por ID
# ===========================================================================

class TestObtenerChat:
    # RF-UI007-TC01
    def test_obtener_chat_exitoso(self, client, mock_chat_service):
        """Sistema abre el chat con su historial de mensajes."""
        mock_chat_service.get_chat.return_value = make_chat_response(chat_id=42)

        response = client.get("/api/v1/chats/42")

        assert response.status_code == 200
        assert response.json()["id"] == 42

    # RF-UI007-TC03
    def test_obtener_chat_no_encontrado(self, client, mock_chat_service):
        """Chat inexistente devuelve 404."""
        mock_chat_service.get_chat.side_effect = NotFoundError("Chat 99 not found")

        response = client.get("/api/v1/chats/99")

        assert response.status_code == 404

    def test_obtener_chat_sin_permisos(self, client, mock_chat_service):
        """Acceder a chat ajeno devuelve 403."""
        mock_chat_service.get_chat.side_effect = ForbiddenError("Access denied")

        response = client.get("/api/v1/chats/5")

        assert response.status_code == 403

    def test_obtener_chat_error_sistema(self, client, mock_chat_service):
        """Error interno al abrir un chat devuelve 500."""
        mock_chat_service.get_chat.side_effect = Exception("Unexpected DB error")

        response = client.get("/api/v1/chats/1")

        assert response.status_code == 500


# ===========================================================================
# PATCH /api/v1/chats/{chat_id} — Actualizar chat
# ===========================================================================

class TestActualizarChat:
    # RF-UI001-TC01 / RF-UI011-TC01
    def test_actualizar_chat_exitoso(self, client, mock_chat_service):
        """Sistema almacena y aplica los cambios de personalización."""
        mock_chat_service.update_chat.return_value = make_chat_response(name="Nuevo Nombre")

        response = client.patch(
            "/api/v1/chats/1",
            json={"name": "Nuevo Nombre"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Nuevo Nombre"

    def test_actualizar_system_prompt(self, client, mock_chat_service):
        """Actualizar system_prompt y response_style se guarda correctamente."""
        mock_chat_service.update_chat.return_value = make_chat_response()

        response = client.patch(
            "/api/v1/chats/1",
            json={
                "system_prompt": "Eres un asistente experto.",
                "response_style": "Responde siempre en español.",
            },
        )

        assert response.status_code == 200

    # RF-UI001-TC03
    def test_actualizar_chat_error_sistema(self, client, mock_chat_service):
        """Confirmar cambios con fallo de sistema devuelve 500."""
        mock_chat_service.update_chat.side_effect = Exception("DB write failed")

        response = client.patch(
            "/api/v1/chats/1",
            json={"name": "Fallo"},
        )

        assert response.status_code == 500

    def test_actualizar_chat_no_encontrado(self, client, mock_chat_service):
        """Actualizar chat inexistente devuelve 404."""
        mock_chat_service.update_chat.side_effect = NotFoundError("Chat not found")

        response = client.patch(
            "/api/v1/chats/99",
            json={"name": "No existe"},
        )

        assert response.status_code == 404

    def test_actualizar_chat_sin_permisos(self, client, mock_chat_service):
        """Actualizar chat ajeno devuelve 403."""
        mock_chat_service.update_chat.side_effect = ForbiddenError()

        response = client.patch(
            "/api/v1/chats/5",
            json={"name": "Intento"},
        )

        assert response.status_code == 403


# ===========================================================================
# DELETE /api/v1/chats/{chat_id} — Eliminar chat
# ===========================================================================

class TestEliminarChat:
    # RF-UI003-TC01
    def test_eliminar_chat_exitoso(self, client, mock_chat_service):
        """Sistema elimina el chat de la vista del usuario (204 sin body)."""
        mock_chat_service.delete_chat.return_value = None

        response = client.delete("/api/v1/chats/1")

        assert response.status_code == 204
        assert response.content == b""

    # RF-UI003-TC03
    def test_eliminar_chat_error_sistema(self, client, mock_chat_service):
        """Confirmación de eliminación con fallo devuelve 500."""
        mock_chat_service.delete_chat.side_effect = Exception("Lock timeout")

        response = client.delete("/api/v1/chats/1")

        assert response.status_code == 500

    def test_eliminar_chat_no_encontrado(self, client, mock_chat_service):
        """Eliminar chat que no existe devuelve 404."""
        mock_chat_service.delete_chat.side_effect = NotFoundError("Chat 99 not found")

        response = client.delete("/api/v1/chats/99")

        assert response.status_code == 404

    def test_eliminar_chat_sin_permisos(self, client, mock_chat_service):
        """Intentar eliminar un chat al que no perteneces devuelve 403."""
        mock_chat_service.delete_chat.side_effect = ForbiddenError()

        response = client.delete("/api/v1/chats/5")

        assert response.status_code == 403
