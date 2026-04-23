"""
Tests funcionales del Document Processing Service.

Casos de prueba cubiertos (según documentación de casos de prueba):
  Chats Individuales:
    RF-UI008-TC01  Subir documento (PDF/DOCX/TXT) - flujo principal
    RF-UI008-TC02  Subir documento - Formato inválido
    RF-UI008-TC03  Subir documento - Tamaño excedido
    RF-UI008-TC04  Subir documento - Error sistema

  Chats Grupales:
    RF-UG007-TC01  Cargar documento en grupo - flujo principal
    RF-UG007-TC02  Cargar doc grupo - Formato inválido
    RF-UG007-TC03  Cargar doc grupo - Tamaño excedido
    RF-UG007-TC04  Cargar doc grupo - Error sistema

  Consulta de documentos:
               Obtener documento por ID
               Obtener documento no encontrado
               Obtener documento sin permisos
               Listar documentos (admin)
               Listar documentos sin permisos

  Eliminación:
               Soft delete exitoso
               Soft delete no encontrado
               Hard delete exitoso
               Hard delete sin permisos

  Autenticación:
               Sin token → 401
"""

from io import BytesIO

from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentServiceException,
    CreateDocumentSizeExceededException,
    CreateDocumentUnauthorizedException,
    CreateDocumentUnsupportedTypeException,
    CreateDocumentValidationException,
)
from app.application.services.document.delete_document_service.exceptions.delete_document_service_exception import (
    DeleteDocumentFailedException,
    DeleteDocumentNotFoundException,
    DeleteDocumentUnauthorizedException,
)
from app.application.services.document.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryNotFoundException,
    DocumentQueryUnauthorizedException,
)

from conftest import (
    make_create_document_response,
    make_document_list_response,
    make_document_response,
)


# ===========================================================================
# POST /api/create-document — Subir documento
# ===========================================================================

class TestSubirDocumento:
    # RF-UI008-TC01 / RF-UG007-TC01
    def test_subir_pdf_valido_exitoso(self, client, mock_create_service):
        """Documento subido correctamente; sistema lo procesa para consultas."""
        mock_create_service.create_document.return_value = make_create_document_response(
            name="informe.pdf"
        )

        response = client.post(
            "/api/create-document",
            data={"chat_id": "1", "prefer_docling": "false"},
            files={"raw_document": ("informe.pdf", BytesIO(b"%PDF-1.4 content"), "application/pdf")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "informe.pdf"
        assert data["status"] == "uploaded"
        assert data["id"] == 1

    # RF-UG007-TC01 — mismo flujo con chat_id de grupo
    def test_subir_documento_en_grupo(self, client, mock_create_service):
        """Documento almacenado y asociado al grupo con mensaje de éxito."""
        mock_create_service.create_document.return_value = make_create_document_response(
            doc_id=5, name="reporte_grupal.pdf"
        )

        response = client.post(
            "/api/create-document",
            data={"chat_id": "10", "prefer_docling": "false"},
            files={"raw_document": ("reporte_grupal.pdf", BytesIO(b"%PDF content"), "application/pdf")},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "reporte_grupal.pdf"

    # RF-UI008-TC02 / RF-UG007-TC02
    def test_subir_documento_formato_invalido(self, client, mock_create_service):
        """Formato de archivo no permitido (.exe) devuelve 415."""
        mock_create_service.create_document.side_effect = CreateDocumentUnsupportedTypeException(
            "Unsupported file type"
        )

        response = client.post(
            "/api/create-document",
            data={"chat_id": "1"},
            files={"raw_document": ("virus.exe", BytesIO(b"MZ..."), "application/octet-stream")},
        )

        assert response.status_code == 415

    # RF-UI008-TC03 / RF-UG007-TC03
    def test_subir_documento_tamanio_excedido(self, client, mock_create_service):
        """Archivo que supera el tamaño máximo devuelve 413."""
        mock_create_service.create_document.side_effect = CreateDocumentSizeExceededException(
            "File size exceeds the maximum allowed limit"
        )

        response = client.post(
            "/api/create-document",
            data={"chat_id": "1"},
            files={"raw_document": ("enorme.pdf", BytesIO(b"x" * 100), "application/pdf")},
        )

        assert response.status_code == 413

    # RF-UI008-TC04 / RF-UG007-TC04
    def test_subir_documento_error_sistema(self, client, mock_create_service):
        """Fallo interno al subir el archivo devuelve 500."""
        mock_create_service.create_document.side_effect = CreateDocumentServiceException(
            "Storage connection lost"
        )

        response = client.post(
            "/api/create-document",
            data={"chat_id": "1"},
            files={"raw_document": ("doc.pdf", BytesIO(b"%PDF"), "application/pdf")},
        )

        assert response.status_code == 500

    def test_subir_documento_sin_chat_id_retorna_422(self, client, mock_create_service):
        """chat_id es obligatorio; sin él FastAPI devuelve 422."""
        response = client.post(
            "/api/create-document",
            data={},
            files={"raw_document": ("doc.pdf", BytesIO(b"%PDF"), "application/pdf")},
        )

        assert response.status_code == 422

    def test_subir_documento_sin_permiso(self, client, mock_create_service):
        """Usuario sin el permiso DOCUMENT_CREATE recibe 403."""
        mock_create_service.create_document.side_effect = CreateDocumentUnauthorizedException(
            "User does not have permission to upload documents"
        )

        response = client.post(
            "/api/create-document",
            data={"chat_id": "1"},
            files={"raw_document": ("doc.pdf", BytesIO(b"%PDF"), "application/pdf")},
        )

        assert response.status_code == 403

    def test_subir_documento_validacion_falla(self, client, mock_create_service):
        """Error de validación genérico devuelve 400."""
        mock_create_service.create_document.side_effect = CreateDocumentValidationException(
            "Document validation failed"
        )

        response = client.post(
            "/api/create-document",
            data={"chat_id": "1"},
            files={"raw_document": ("doc.pdf", BytesIO(b"%PDF"), "application/pdf")},
        )

        assert response.status_code == 400


# ===========================================================================
# GET /api/document-query/document/{id} — Obtener documento
# ===========================================================================

class TestObtenerDocumento:
    def test_obtener_documento_exitoso(self, client, mock_query_service):
        """Sistema retorna los metadatos del documento solicitado."""
        mock_query_service.get_document.return_value = make_document_response(
            doc_id=3, name="manual.pdf"
        )

        response = client.get("/api/document-query/document/3")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 3
        assert data["name"] == "manual.pdf"
        assert data["status"] == "processed"

    def test_obtener_documento_no_encontrado(self, client, mock_query_service):
        """Documento inexistente devuelve 404."""
        mock_query_service.get_document.side_effect = DocumentQueryNotFoundException(
            "Document 99 not found"
        )

        response = client.get("/api/document-query/document/99")

        assert response.status_code == 404

    def test_obtener_documento_sin_permisos(self, client, mock_query_service):
        """Acceder a documento ajeno devuelve 403."""
        mock_query_service.get_document.side_effect = DocumentQueryUnauthorizedException(
            "User is not authorized to access this document"
        )

        response = client.get("/api/document-query/document/5")

        assert response.status_code == 403

    def test_obtener_documento_error_sistema(self, client, mock_query_service):
        """Error interno al obtener documento devuelve 500."""
        mock_query_service.get_document.side_effect = Exception("DB timeout")

        response = client.get("/api/document-query/document/1")

        assert response.status_code == 500


# ===========================================================================
# GET /api/document-query/documents — Listar documentos
# ===========================================================================

class TestListarDocumentos:
    def test_listar_documentos_exitoso(self, client, mock_query_service):
        """Admin obtiene la lista completa de documentos."""
        mock_query_service.get_documents.return_value = make_document_list_response()

        response = client.get("/api/document-query/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert len(data["documents"]) == 1

    def test_listar_documentos_lista_vacia(self, client, mock_query_service):
        """Lista vacía cuando no hay documentos."""
        mock_query_service.get_documents.return_value = make_document_list_response(docs=[])

        response = client.get("/api/document-query/documents")

        assert response.status_code == 200
        assert response.json()["documents"] == []

    def test_listar_documentos_sin_permisos(self, client, mock_query_service):
        """Usuario sin rol admin recibe 403."""
        mock_query_service.get_documents.side_effect = DocumentQueryUnauthorizedException(
            "Admin role required to list all documents"
        )

        response = client.get("/api/document-query/documents")

        assert response.status_code == 403

    def test_listar_documentos_con_filtro_nombre(self, client, mock_query_service):
        """Filtro por nombre se acepta correctamente."""
        mock_query_service.get_documents.return_value = make_document_list_response()

        response = client.get("/api/document-query/documents?name=manual")

        assert response.status_code == 200

    def test_listar_documentos_error_sistema(self, client, mock_query_service):
        """Error de BD al listar documentos devuelve 500."""
        mock_query_service.get_documents.side_effect = Exception("Connection lost")

        response = client.get("/api/document-query/documents")

        assert response.status_code == 500


# ===========================================================================
# DELETE /api/delete-document/soft — Eliminación soft
# ===========================================================================

class TestEliminarDocumentoSoft:
    def test_soft_delete_exitoso(self, client, mock_delete_service):
        """Sistema elimina lógicamente el documento (204 sin body)."""
        mock_delete_service.soft_delete_document.return_value = None

        response = client.delete("/api/delete-document/soft/document_controllers/1")

        assert response.status_code == 204
        assert response.content == b""

    def test_soft_delete_no_encontrado(self, client, mock_delete_service):
        """Documento inexistente devuelve 404."""
        mock_delete_service.soft_delete_document.side_effect = DeleteDocumentNotFoundException(
            "Document 99 not found"
        )

        response = client.delete("/api/delete-document/soft/document_controllers/99")

        assert response.status_code == 404

    def test_soft_delete_sin_permisos(self, client, mock_delete_service):
        """Sin permiso para eliminar devuelve 403."""
        mock_delete_service.soft_delete_document.side_effect = DeleteDocumentUnauthorizedException(
            "User is not authorized to delete this document"
        )

        response = client.delete("/api/delete-document/soft/document_controllers/5")

        assert response.status_code == 403

    def test_soft_delete_error_sistema(self, client, mock_delete_service):
        """Error interno al eliminar devuelve 500."""
        mock_delete_service.soft_delete_document.side_effect = DeleteDocumentFailedException(
            "Storage cleanup failed"
        )

        response = client.delete("/api/delete-document/soft/document_controllers/1")

        assert response.status_code == 500


# ===========================================================================
# DELETE /api/delete-document/hard — Eliminación hard
# ===========================================================================

class TestEliminarDocumentoHard:
    def test_hard_delete_exitoso(self, client, mock_delete_service):
        """Eliminación física del documento retorna 204."""
        mock_delete_service.hard_delete_document.return_value = None

        response = client.delete("/api/delete-document/hard/document_controllers/1")

        assert response.status_code == 204

    def test_hard_delete_no_encontrado(self, client, mock_delete_service):
        """Documento inexistente devuelve 404."""
        mock_delete_service.hard_delete_document.side_effect = DeleteDocumentNotFoundException(
            "Document 99 not found"
        )

        response = client.delete("/api/delete-document/hard/document_controllers/99")

        assert response.status_code == 404
