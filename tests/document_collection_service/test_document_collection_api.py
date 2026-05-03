"""
Tests funcionales del Document Collection Service.

Casos de prueba cubiertos (según documentación "De Administrador"):

  RF-A015 — Crear colección de documentos:
    TC01  Crear colección exitosamente
    TC02  Nombre vacío → 400
    TC03  Campo requerido ausente → 400
    TC04  Error del sistema → 500

  RF-A016 — Eliminar colección de documentos:
    TC01  Eliminar exitosamente → 204
    TC03  Colección inexistente → 404
    TC04  Error del sistema → 500

  RF-A013 — Añadir documento a colección:
    TC01  Añadir exitosamente → 201
    TC03  Colección inexistente → 404
    TC04  Documento inexistente → 404
    TC05  Error del sistema → 500

  RF-A014 — Eliminar documento de colección:
    TC01  Eliminar exitosamente → 204
    TC03  Colección inexistente → 404
    TC04  Error del sistema → 500

  RF-A017 — Añadir usuario a colección:
    TC01  Añadir exitosamente → 201
    TC02  Usuario ya miembro → 409
    TC03  Error del sistema → 500

  RF-A018 — Sacar usuario de colección:
    TC01  Eliminar exitosamente → 204
    TC02  Error del sistema → 500
"""

from core.domain.document_collection_exceptions import (
    CollectionNotFoundException,
    DocumentNotAvailableException,
    DuplicateMembershipException,
)
from conftest import make_collection, make_document_link, make_membership, make_profiles_result


# ===========================================================================
# POST /api/v1/document-collections/
# ===========================================================================

class TestCrearColeccion:
    # RF-A015-TC01
    def test_crear_coleccion_exitoso(self, client, mock_collection_service):
        mock_collection_service.create_document_collection.return_value = make_collection(name="Proyecto Alpha")

        response = client.post("/api/v1/document-collections/", data={"name": "Proyecto Alpha"}, format="json")

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Proyecto Alpha"

    # RF-A015-TC02
    def test_crear_coleccion_nombre_vacio_retorna_400(self, client, mock_collection_service):
        response = client.post("/api/v1/document-collections/", data={"name": ""}, format="json")

        assert response.status_code == 400
        mock_collection_service.create_document_collection.assert_not_called()

    # RF-A015-TC03
    def test_crear_coleccion_sin_nombre_retorna_400(self, client, mock_collection_service):
        response = client.post("/api/v1/document-collections/", data={}, format="json")

        assert response.status_code == 400
        mock_collection_service.create_document_collection.assert_not_called()

    # RF-A015-TC04
    def test_crear_coleccion_error_sistema_retorna_500(self, client, mock_collection_service):
        mock_collection_service.create_document_collection.side_effect = Exception("DB error")

        response = client.post("/api/v1/document-collections/", data={"name": "Colección"}, format="json")

        assert response.status_code == 500
        assert response.json()["error"] == "internal_error"


# ===========================================================================
# DELETE /api/v1/document-collections/{id}/
# ===========================================================================

class TestEliminarColeccion:
    # RF-A016-TC01
    def test_eliminar_coleccion_exitoso(self, client, mock_collection_service):
        mock_collection_service.delete_document_collection.return_value = None

        response = client.delete("/api/v1/document-collections/1/")

        assert response.status_code == 204
        mock_collection_service.delete_document_collection.assert_called_once()

    # RF-A016-TC03
    def test_eliminar_coleccion_inexistente_retorna_404(self, client, mock_collection_service):
        mock_collection_service.delete_document_collection.side_effect = CollectionNotFoundException()

        response = client.delete("/api/v1/document-collections/99/")

        assert response.status_code == 404
        assert response.json()["error"] == "document_collection_not_found"

    # RF-A016-TC04
    def test_eliminar_coleccion_error_sistema_retorna_500(self, client, mock_collection_service):
        mock_collection_service.delete_document_collection.side_effect = Exception("Storage failure")

        response = client.delete("/api/v1/document-collections/1/")

        assert response.status_code == 500
        assert response.json()["error"] == "internal_error"


# ===========================================================================
# POST /api/v1/document-collections/{id}/documents/
# ===========================================================================

class TestAnadirDocumentoAColeccion:
    # RF-A013-TC01
    def test_anadir_documento_exitoso(self, client, mock_document_service):
        mock_document_service.add_document_collection_document.return_value = make_document_link()

        response = client.post("/api/v1/document-collections/1/documents/", data={"document_id": 10}, format="json")

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 1
        assert data["document"]["id"] == 10

    # RF-A013-TC03
    def test_anadir_documento_coleccion_inexistente_retorna_404(self, client, mock_document_service):
        mock_document_service.add_document_collection_document.side_effect = CollectionNotFoundException()

        response = client.post("/api/v1/document-collections/99/documents/", data={"document_id": 10}, format="json")

        assert response.status_code == 404
        assert response.json()["error"] == "document_collection_not_found"

    # RF-A013-TC04
    def test_anadir_documento_inexistente_retorna_404(self, client, mock_document_service):
        mock_document_service.add_document_collection_document.side_effect = DocumentNotAvailableException()

        response = client.post("/api/v1/document-collections/1/documents/", data={"document_id": 999}, format="json")

        assert response.status_code == 404
        assert response.json()["error"] == "document_not_available"

    # RF-A013-TC05
    def test_anadir_documento_error_sistema_retorna_500(self, client, mock_document_service):
        mock_document_service.add_document_collection_document.side_effect = Exception("Unexpected error")

        response = client.post("/api/v1/document-collections/1/documents/", data={"document_id": 10}, format="json")

        assert response.status_code == 500
        assert response.json()["error"] == "internal_error"


# ===========================================================================
# DELETE /api/v1/document-collections/{id}/documents/{id}/
# ===========================================================================

class TestEliminarDocumentoDeColeccion:
    # RF-A014-TC01
    def test_eliminar_documento_exitoso(self, client, mock_document_service):
        mock_document_service.remove_document_collection_document.return_value = None

        response = client.delete("/api/v1/document-collections/1/documents/10/")

        assert response.status_code == 204
        mock_document_service.remove_document_collection_document.assert_called_once()

    # RF-A014-TC03
    def test_eliminar_documento_coleccion_inexistente_retorna_404(self, client, mock_document_service):
        mock_document_service.remove_document_collection_document.side_effect = CollectionNotFoundException()

        response = client.delete("/api/v1/document-collections/99/documents/10/")

        assert response.status_code == 404
        assert response.json()["error"] == "document_collection_not_found"

    # RF-A014-TC04
    def test_eliminar_documento_error_sistema_retorna_500(self, client, mock_document_service):
        mock_document_service.remove_document_collection_document.side_effect = Exception("IO error")

        response = client.delete("/api/v1/document-collections/1/documents/10/")

        assert response.status_code == 500
        assert response.json()["error"] == "internal_error"


# ===========================================================================
# POST /api/v1/document-collections/{id}/users/
# ===========================================================================

class TestAnadirUsuarioAColeccion:
    # RF-A017-TC01
    def test_anadir_usuario_exitoso(self, client, mock_user_service, mock_profile_client):
        mock_user_service.add_document_collection_user.return_value = make_membership(user_id=2)
        mock_profile_client.fetch_by_ids.return_value = make_profiles_result(user_id=2)

        response = client.post("/api/v1/document-collections/1/users/", data={"user_id": 2}, format="json")

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 1
        assert data["user"]["id"] == 2
        assert "profiles_enrichment" in data

    # RF-A017-TC02
    def test_anadir_usuario_duplicado_retorna_409(self, client, mock_user_service):
        mock_user_service.add_document_collection_user.side_effect = DuplicateMembershipException()

        response = client.post("/api/v1/document-collections/1/users/", data={"user_id": 2}, format="json")

        assert response.status_code == 409
        assert response.json()["error"] == "duplicate_membership"

    # RF-A017-TC03
    def test_anadir_usuario_error_sistema_retorna_500(self, client, mock_user_service):
        mock_user_service.add_document_collection_user.side_effect = Exception("Service down")

        response = client.post("/api/v1/document-collections/1/users/", data={"user_id": 2}, format="json")

        assert response.status_code == 500
        assert response.json()["error"] == "internal_error"


# ===========================================================================
# DELETE /api/v1/document-collections/{id}/users/{id}/
# ===========================================================================

class TestEliminarUsuarioDeColeccion:
    # RF-A018-TC01
    def test_eliminar_usuario_exitoso(self, client, mock_user_service):
        mock_user_service.remove_document_collection_user.return_value = None

        response = client.delete("/api/v1/document-collections/1/users/2/")

        assert response.status_code == 204
        mock_user_service.remove_document_collection_user.assert_called_once()

    # RF-A018-TC02
    def test_eliminar_usuario_error_sistema_retorna_500(self, client, mock_user_service):
        mock_user_service.remove_document_collection_user.side_effect = Exception("DB timeout")

        response = client.delete("/api/v1/document-collections/1/users/2/")

        assert response.status_code == 500
        assert response.json()["error"] == "internal_error"
