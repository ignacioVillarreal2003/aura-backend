"""
Tests funcionales del Notification Service.

Casos de prueba cubiertos (según documentación de casos de prueba):

  RF-A011 / RF-U006 — Ver Notificaciones:
    TC01  Usuario autenticado → 200 lista paginada        (RF-A011-TC01, RF-U006-TC01)
    TC02  Filtro por estado → 200 filtrada
    TC03  Sin token → 401                                 (RF-A011-TC03, RF-U006-TC02)
    TC04  Lista vacía → 200 con count=0

  RF-A010 — Crear Notificación (admin → usuario):
    TC01  Crear para un receptor → 201                   (RF-A010-TC01)
    TC02  Crear para múltiples receptores → 201
    TC03  Campos requeridos ausentes → 400
    TC04  Sin token → 401                                 (RF-A010-TC03)
    TC05  Error de sistema → 500

  Actualizar Estado de Notificación (RF-U008):
    TC01  Marcar como leída → 200
    TC02  Marcar como archivada → 200
    TC03  Notificación no encontrada (o no es propietario) → 404
    TC04  Estado inválido → 400
    TC05  Sin token → 401

  Eliminar Notificación (soft delete):
    TC01  Propietario elimina → 204
    TC02  No es propietario → 404
    TC03  Sin token → 401

  Eliminar Notificación (hard delete, superadmin):
    TC01  Superadmin → 204
    TC02  Usuario no superadmin → 403
    TC03  Notificación no existe → 404
    TC04  Sin token → 401

  POST /api/internal/notifications/admin-create/ (RF-A010):
    TC01  Token interno válido → 201                     (RF-A010-TC01)
    TC02  Token interno inválido → 401
    TC03  Campos requeridos ausentes → 400
"""

from unittest.mock import patch
from conftest import (
    make_notification, make_mock_queryset,
    USER_ID, ADMIN_USER_ID, INTERNAL_TOKEN,
)


# ===========================================================================
# GET /api/notifications/
# ===========================================================================

class TestListarNotificaciones:

    # RF-A011-TC01 / RF-U006-TC01 — Lista paginada para usuario autenticado
    def test_listar_notificaciones_autenticado_retorna_200(
        self, client, mock_get_user, mock_notification_manager
    ):
        notif = make_notification()
        mock_notification_manager.filter.return_value = make_mock_queryset([notif])

        response = client.get("/api/notifications/")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["count"] == 1
        assert len(data["results"]) == 1

    # Filtro por estado (query param ?status=unread)
    def test_listar_notificaciones_filtradas_por_estado_retorna_200(
        self, client, mock_get_user, mock_notification_manager
    ):
        notif = make_notification(status="unread")
        qs = make_mock_queryset([notif])
        mock_notification_manager.filter.return_value = qs

        response = client.get("/api/notifications/?status=unread")

        assert response.status_code == 200
        assert response.json()["count"] == 1

    # RF-A011-TC02 / RF-U006-TC02 — Sin token → 401
    def test_listar_notificaciones_sin_token_retorna_401(
        self, client, mock_notification_manager
    ):
        with patch("notifications.api.views.get_user_from_request", return_value=None):
            response = client.get("/api/notifications/")

        assert response.status_code == 401

    # Lista vacía → 200 con count=0
    def test_listar_notificaciones_sin_resultados_retorna_200_vacio(
        self, client, mock_get_user, mock_notification_manager
    ):
        mock_notification_manager.filter.return_value = make_mock_queryset([])

        response = client.get("/api/notifications/")

        assert response.status_code == 200
        assert response.json()["count"] == 0
        assert response.json()["results"] == []


# ===========================================================================
# POST /api/notifications/
# ===========================================================================

class TestCrearNotificacion:

    # RF-A010-TC01 — Crear notificación para un receptor
    def test_crear_notificacion_un_receptor_retorna_201(
        self, client, mock_get_user, mock_notification_manager
    ):
        response = client.post(
            "/api/notifications/",
            data={
                "receiver_ids": [USER_ID],
                "message": "Tienes una nueva tarea asignada",
                "type": "admin",
            },
            format="json",
        )

        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 1
        assert len(data["notifications"]) == 1

    # Crear notificación para múltiples receptores
    def test_crear_notificacion_multiples_receptores_retorna_201(
        self, client, mock_get_user, mock_notification_manager
    ):
        response = client.post(
            "/api/notifications/",
            data={
                "receiver_ids": [1, 2, 3],
                "message": "Actualización del sistema programada",
                "type": "system",
                "target_scope": "system",
            },
            format="json",
        )

        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 3
        assert len(data["notifications"]) == 3

    # Campos requeridos ausentes → 400
    def test_crear_notificacion_sin_campos_requeridos_retorna_400(
        self, client, mock_get_user, mock_notification_manager
    ):
        response = client.post(
            "/api/notifications/",
            data={"receiver_ids": [USER_ID]},
            format="json",
        )

        assert response.status_code == 400
        mock_notification_manager.bulk_create.assert_not_called()

    # Lista de receptores vacía → 400
    def test_crear_notificacion_sin_receptores_retorna_400(
        self, client, mock_get_user, mock_notification_manager
    ):
        response = client.post(
            "/api/notifications/",
            data={"receiver_ids": [], "message": "Hola", "type": "admin"},
            format="json",
        )

        assert response.status_code == 400
        mock_notification_manager.bulk_create.assert_not_called()

    # RF-A010-TC03 — Sin token → 401
    def test_crear_notificacion_sin_token_retorna_401(
        self, client, mock_notification_manager
    ):
        with patch("notifications.api.views.get_user_from_request", return_value=None):
            response = client.post(
                "/api/notifications/",
                data={"receiver_ids": [USER_ID], "message": "Test", "type": "admin"},
                format="json",
            )

        assert response.status_code == 401
        mock_notification_manager.bulk_create.assert_not_called()

    # Error de sistema → 500
    def test_crear_notificacion_error_sistema_retorna_500(
        self, client, mock_get_user, mock_notification_manager
    ):
        mock_notification_manager.bulk_create.side_effect = Exception("DB timeout")

        response = client.post(
            "/api/notifications/",
            data={"receiver_ids": [USER_ID], "message": "Test", "type": "admin"},
            format="json",
        )

        assert response.status_code == 500


# ===========================================================================
# PATCH /api/notifications/<pk>/status/
# ===========================================================================

class TestActualizarEstadoNotificacion:

    # Marcar como leída → 200
    def test_marcar_como_leida_retorna_200(
        self, client, mock_get_user, mock_notification_manager
    ):
        notif = make_notification(receiver_id=USER_ID, status="unread")
        mock_notification_manager.filter.return_value.first.return_value = notif

        response = client.patch(
            "/api/notifications/1/status/",
            data={"status": "read"},
            format="json",
        )

        assert response.status_code == 200
        notif.save.assert_called_once()

    # Marcar como archivada → 200
    def test_marcar_como_archivada_retorna_200(
        self, client, mock_get_user, mock_notification_manager
    ):
        notif = make_notification(receiver_id=USER_ID, status="unread")
        mock_notification_manager.filter.return_value.first.return_value = notif

        response = client.patch(
            "/api/notifications/1/status/",
            data={"status": "archived"},
            format="json",
        )

        assert response.status_code == 200
        notif.save.assert_called_once()

    # Notificación no existe o no pertenece al usuario → 404
    def test_notificacion_no_encontrada_retorna_404(
        self, client, mock_get_user, mock_notification_manager
    ):
        mock_notification_manager.filter.return_value.first.return_value = None

        response = client.patch(
            "/api/notifications/999/status/",
            data={"status": "read"},
            format="json",
        )

        assert response.status_code == 404

    # Estado inválido → 400
    def test_estado_invalido_retorna_400(
        self, client, mock_get_user, mock_notification_manager
    ):
        response = client.patch(
            "/api/notifications/1/status/",
            data={"status": "inexistente"},
            format="json",
        )

        assert response.status_code == 400

    # Sin token → 401
    def test_actualizar_estado_sin_token_retorna_401(
        self, client, mock_notification_manager
    ):
        with patch("notifications.api.views.get_user_from_request", return_value=None):
            response = client.patch(
                "/api/notifications/1/status/",
                data={"status": "read"},
                format="json",
            )

        assert response.status_code == 401


# ===========================================================================
# DELETE /api/notifications/<pk>/   (soft delete)
# ===========================================================================

class TestEliminarNotificacion:

    # Propietario elimina con soft delete → 204
    def test_eliminar_notificacion_propietario_retorna_204(
        self, client, mock_get_user, mock_notification_manager
    ):
        notif = make_notification(receiver_id=USER_ID)
        mock_notification_manager.filter.return_value.first.return_value = notif

        response = client.delete("/api/notifications/1/")

        assert response.status_code == 204
        notif.save.assert_called_once()

    # Notificación no pertenece al usuario → 404
    def test_eliminar_notificacion_ajena_retorna_404(
        self, client, mock_get_user, mock_notification_manager
    ):
        mock_notification_manager.filter.return_value.first.return_value = None

        response = client.delete("/api/notifications/99/")

        assert response.status_code == 404

    # Sin token → 401
    def test_eliminar_notificacion_sin_token_retorna_401(
        self, client, mock_notification_manager
    ):
        with patch("notifications.api.views.get_user_from_request", return_value=None):
            response = client.delete("/api/notifications/1/")

        assert response.status_code == 401


# ===========================================================================
# DELETE /api/notifications/<pk>/hard/   (hard delete, superadmin)
# ===========================================================================

class TestEliminarNotificacionHard:

    # Superadmin elimina permanentemente → 204
    def test_hard_delete_superadmin_retorna_204(
        self, client, mock_super_admin, mock_notification_manager
    ):
        notif = make_notification()
        mock_notification_manager.filter.return_value.first.return_value = notif

        response = client.delete("/api/notifications/1/hard/")

        assert response.status_code == 204
        notif.delete.assert_called_once()

    # Usuario sin superadmin → 403
    def test_hard_delete_sin_superadmin_retorna_403(
        self, client, mock_get_user, mock_notification_manager
    ):
        response = client.delete("/api/notifications/1/hard/")

        assert response.status_code == 403

    # Notificación no existe → 404
    def test_hard_delete_notificacion_inexistente_retorna_404(
        self, client, mock_super_admin, mock_notification_manager
    ):
        mock_notification_manager.filter.return_value.first.return_value = None

        response = client.delete("/api/notifications/999/hard/")

        assert response.status_code == 404

    # Sin token → 401
    def test_hard_delete_sin_token_retorna_401(
        self, client, mock_notification_manager
    ):
        with patch("notifications.api.views.get_user_from_request", return_value=None):
            response = client.delete("/api/notifications/1/hard/")

        assert response.status_code == 401


# ===========================================================================
# POST /api/internal/notifications/admin-create/
# ===========================================================================

class TestCrearNotificacionInterna:

    # RF-A010-TC01 — Token interno válido → 201
    def test_admin_create_token_valido_retorna_201(
        self, client, mock_notification_manager
    ):
        response = client.post(
            "/api/internal/notifications/admin-create/",
            data={
                "receiver_ids": [USER_ID],
                "message": "El administrador te ha enviado un mensaje",
                "type": "admin",
                "actor_user_id": ADMIN_USER_ID,
            },
            format="json",
            HTTP_X_INTERNAL_TOKEN=INTERNAL_TOKEN,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 1

    # Token interno inválido → 401
    def test_admin_create_token_invalido_retorna_401(
        self, client, mock_notification_manager
    ):
        response = client.post(
            "/api/internal/notifications/admin-create/",
            data={
                "receiver_ids": [USER_ID],
                "message": "Test",
                "type": "admin",
            },
            format="json",
            HTTP_X_INTERNAL_TOKEN="token-incorrecto",
        )

        assert response.status_code == 401
        mock_notification_manager.bulk_create.assert_not_called()

    # Sin token interno → 401
    def test_admin_create_sin_token_retorna_401(
        self, client, mock_notification_manager
    ):
        response = client.post(
            "/api/internal/notifications/admin-create/",
            data={
                "receiver_ids": [USER_ID],
                "message": "Test",
                "type": "admin",
            },
            format="json",
        )

        assert response.status_code == 401

    # Campos requeridos ausentes → 400
    def test_admin_create_sin_campos_requeridos_retorna_400(
        self, client, mock_notification_manager
    ):
        response = client.post(
            "/api/internal/notifications/admin-create/",
            data={"receiver_ids": [USER_ID]},
            format="json",
            HTTP_X_INTERNAL_TOKEN=INTERNAL_TOKEN,
        )

        assert response.status_code == 400
        mock_notification_manager.bulk_create.assert_not_called()
