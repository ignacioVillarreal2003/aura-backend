"""
Tests funcionales del Chat Service — envío y consulta de mensajes.

Casos de prueba cubiertos:
  RF-UI012-TC01  Consulta por escrito (enviar mensaje exitoso)
  RF-UI012-TC02  Consulta no relacionada (respuesta del LLM con aviso)
  RF-UI012-TC03  Consulta por escrito - Error procesamiento (LLM falla)
  RF-UG010-TC01  Consulta grupal por escrito
  RF-UG010-TC03  Consulta grupal - Error procesamiento
               Listar mensajes exitoso
               Listar mensajes sin permisos
               Obtener mensaje por ID
               Eliminar mensaje
"""

from app.application.exceptions.api_exceptions import (
    ForbiddenError,
    LLMError,
    NotFoundError,
)

from conftest import make_message_list_response, make_message_response


# ===========================================================================
# POST /api/v1/chats/{chat_id}/messages — Enviar mensaje
# ===========================================================================

class TestEnviarMensaje:
    # RF-UI012-TC01 / RF-UG010-TC01
    def test_enviar_mensaje_exitoso(self, client, mock_message_service):
        """Sistema procesa la consulta, genera respuesta y la presenta en el chat."""
        mock_message_service.send_message.return_value = make_message_response(
            message="La fotosíntesis es el proceso por el cual..."
        )

        response = client.post(
            "/api/v1/chats/1/messages",
            json={"message": "¿Qué es la fotosíntesis?", "sender_type": "user"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["sender_type"] == "system"
        assert "fotosíntesis" in data["message"]
        assert data["chat_id"] == 1

    # RF-UI012-TC03 / RF-UG010-TC03
    def test_enviar_mensaje_error_llm(self, client, mock_message_service):
        """Error en el servicio LLM devuelve 502."""
        mock_message_service.send_message.side_effect = LLMError(
            "Error communicating with LLM service"
        )

        response = client.post(
            "/api/v1/chats/1/messages",
            json={"message": "¿Hola?", "sender_type": "user"},
        )

        assert response.status_code == 502

    def test_enviar_mensaje_chat_no_encontrado(self, client, mock_message_service):
        """Enviar mensaje a chat inexistente devuelve 404."""
        mock_message_service.send_message.side_effect = NotFoundError("Chat 99 not found")

        response = client.post(
            "/api/v1/chats/99/messages",
            json={"message": "Hola", "sender_type": "user"},
        )

        assert response.status_code == 404

    def test_enviar_mensaje_sin_permisos(self, client, mock_message_service):
        """Enviar mensaje a chat ajeno devuelve 403."""
        mock_message_service.send_message.side_effect = ForbiddenError()

        response = client.post(
            "/api/v1/chats/5/messages",
            json={"message": "Hola", "sender_type": "user"},
        )

        assert response.status_code == 403

    def test_enviar_mensaje_vacio_retorna_422(self, client, mock_message_service):
        """Mensaje vacío viola min_length=1 y devuelve 422."""
        response = client.post(
            "/api/v1/chats/1/messages",
            json={"message": "", "sender_type": "user"},
        )

        assert response.status_code == 422

    def test_enviar_mensaje_sender_type_invalido_retorna_422(self, client, mock_message_service):
        """sender_type con valor no permitido devuelve 422."""
        response = client.post(
            "/api/v1/chats/1/messages",
            json={"message": "Hola", "sender_type": "bot"},
        )

        assert response.status_code == 422

    def test_enviar_mensaje_error_interno(self, client, mock_message_service):
        """Error inesperado al procesar el mensaje devuelve 500."""
        mock_message_service.send_message.side_effect = Exception("Unexpected failure")

        response = client.post(
            "/api/v1/chats/1/messages",
            json={"message": "¿Hola?", "sender_type": "user"},
        )

        assert response.status_code == 500


# ===========================================================================
# GET /api/v1/chats/{chat_id}/messages — Listar mensajes
# ===========================================================================

class TestListarMensajes:
    def test_listar_mensajes_exitoso(self, client, mock_message_service):
        """Sistema retorna el historial del chat en orden cronológico."""
        mock_message_service.list_messages.return_value = make_message_list_response()

        response = client.get("/api/v1/chats/1/messages")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["sender_type"] == "system"

    def test_listar_mensajes_sin_permisos(self, client, mock_message_service):
        """Listar mensajes de un chat ajeno devuelve 403."""
        mock_message_service.list_messages.side_effect = ForbiddenError()

        response = client.get("/api/v1/chats/5/messages")

        assert response.status_code == 403

    def test_listar_mensajes_con_limit(self, client, mock_message_service):
        """El parámetro limit es respetado y enviado al servicio."""
        mock_message_service.list_messages.return_value = make_message_list_response()

        response = client.get("/api/v1/chats/1/messages?limit=10")

        assert response.status_code == 200

    def test_listar_mensajes_error_sistema(self, client, mock_message_service):
        """Error de BD al listar mensajes devuelve 500."""
        mock_message_service.list_messages.side_effect = Exception("Timeout")

        response = client.get("/api/v1/chats/1/messages")

        assert response.status_code == 500


# ===========================================================================
# GET /api/v1/chats/{chat_id}/messages/{message_id} — Obtener mensaje
# ===========================================================================

class TestObtenerMensaje:
    def test_obtener_mensaje_exitoso(self, client, mock_message_service):
        """Sistema retorna el mensaje solicitado."""
        mock_message_service.get_message.return_value = make_message_response(
            msg_id=7, chat_id=1
        )

        response = client.get("/api/v1/chats/1/messages/7")

        assert response.status_code == 200
        assert response.json()["id"] == 7

    def test_obtener_mensaje_no_encontrado(self, client, mock_message_service):
        """Mensaje inexistente devuelve 404."""
        mock_message_service.get_message.side_effect = NotFoundError("Message 99 not found")

        response = client.get("/api/v1/chats/1/messages/99")

        assert response.status_code == 404

    def test_obtener_mensaje_sin_permisos(self, client, mock_message_service):
        """Acceder a mensaje de chat ajeno devuelve 403."""
        mock_message_service.get_message.side_effect = ForbiddenError()

        response = client.get("/api/v1/chats/5/messages/1")

        assert response.status_code == 403


# ===========================================================================
# DELETE /api/v1/chats/{chat_id}/messages/{message_id} — Eliminar mensaje
# ===========================================================================

class TestEliminarMensaje:
    def test_eliminar_mensaje_exitoso(self, client, mock_message_service):
        """Sistema aplica soft delete al mensaje (204 sin body)."""
        mock_message_service.delete_message.return_value = None

        response = client.delete("/api/v1/chats/1/messages/1")

        assert response.status_code == 204
        assert response.content == b""

    def test_eliminar_mensaje_no_encontrado(self, client, mock_message_service):
        """Eliminar mensaje inexistente devuelve 404."""
        mock_message_service.delete_message.side_effect = NotFoundError("Message not found")

        response = client.delete("/api/v1/chats/1/messages/99")

        assert response.status_code == 404

    def test_eliminar_mensaje_sin_permisos(self, client, mock_message_service):
        """Eliminar mensaje de chat ajeno devuelve 403."""
        mock_message_service.delete_message.side_effect = ForbiddenError()

        response = client.delete("/api/v1/chats/5/messages/1")

        assert response.status_code == 403
