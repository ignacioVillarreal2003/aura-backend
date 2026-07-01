import pytest
from unittest.mock import MagicMock, patch
from django.http import Http404
from apps.documents.models import Document
from apps.documents.admin import DocumentAdmin

class TestAdminChatDocs:
    def test_get_queryset_excludes_chat_documents(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        site = AdminSite()
        doc_admin = DocumentAdmin(Document, site)

        # Mock the parent get_queryset to return a mock queryset
        mock_qs = MagicMock()
        with patch('django.contrib.admin.ModelAdmin.get_queryset', return_value=mock_qs):
            request = RequestFactory().get('/admin/documents/document/')
            request.user = MagicMock()

            doc_admin.get_queryset(request)

            # Assert that the queryset was filtered for chat_id__isnull=True
            mock_qs.filter.assert_any_call(chat_id__isnull=True)

    def test_changeform_view_raises_404_for_chat_doc(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        site = AdminSite()
        doc_admin = DocumentAdmin(Document, site)

        # Mock Document.objects.get to return a mock document with chat_id = 123
        mock_doc = MagicMock()
        mock_doc.chat_id = 123

        with patch('apps.documents.models.Document.objects.get', return_value=mock_doc):
            request = RequestFactory().get('/admin/documents/document/999/change/')
            request.user = MagicMock()

            with pytest.raises(Http404):
                doc_admin.changeform_view(request, object_id='999')

    def test_history_view_raises_404_for_chat_doc(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        site = AdminSite()
        doc_admin = DocumentAdmin(Document, site)

        # Mock Document.objects.get to return a mock document with chat_id = 123
        mock_doc = MagicMock()
        mock_doc.chat_id = 123

        with patch('apps.documents.models.Document.objects.get', return_value=mock_doc):
            request = RequestFactory().get('/admin/documents/document/999/history/')
            request.user = MagicMock()

            with pytest.raises(Http404):
                doc_admin.history_view(request, object_id='999')

    def test_get_actions_allows_admin_user(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        site = AdminSite()
        doc_admin = DocumentAdmin(Document, site)

        request = RequestFactory().get('/admin/documents/document/')
        request.user = MagicMock()

        # When requester is a regular admin
        with patch('apps.documents.admin._is_admin_or_super_user', return_value=True):
            actions = doc_admin.get_actions(request)
            assert 'action_reprocess' in actions
            assert 'action_reembed' in actions
            assert 'action_enrich' in actions
            assert 'action_graph_extract' in actions

        # When requester is NOT even a regular admin
        with patch('apps.documents.admin._is_admin_or_super_user', return_value=False):
            actions = doc_admin.get_actions(request)
            assert 'action_reprocess' not in actions
            assert 'action_reembed' not in actions
            assert 'action_enrich' not in actions
            assert 'action_graph_extract' not in actions
