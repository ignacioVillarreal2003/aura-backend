from django.urls import path

from apps.chat.views.chat_content_views import ClearChatContentView, MarkChatAsReadView
from apps.chat.views.chat_export_view import (
    ChatExportMarkdownView,
    ChatExportPDFView,
    ChatManageExportMarkdownView,
    ChatManageExportPDFView,
)
from apps.chat.views.chat_view import ChatViewSet
from apps.chat.views.share_link_view import ShareLinkDetailView, ShareLinkListView
from apps.chat.views.transcribe_view import TranscribeView

_v = ChatViewSet

urlpatterns = [
    path("", _v.as_view({"get": "list", "post": "create"}), name="chat-list"),
    path("manage/", _v.as_view({"get": "manage"}), name="chat-manage"),
    path("me/", _v.as_view({"get": "my_chats"}), name="chat-me"),
    path("archived/", _v.as_view({"get": "archived"}), name="chat-archived"),
    path("archive/", _v.as_view({"post": "archive"}), name="chat-archive"),
    path("unarchive/", _v.as_view({"post": "unarchive"}), name="chat-unarchive"),
    path("delete/", _v.as_view({"post": "delete_bulk"}), name="chat-delete-bulk"),
    path("<int:chat_id>/", _v.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
         name="chat-detail"),
    path("<int:chat_id>/pin/", _v.as_view({"post": "pin", "delete": "pin"}), name="chat-pin"),
    path("<int:chat_id>/lock/", _v.as_view({"post": "lock", "delete": "lock"}), name="chat-lock"),
    path("<int:chat_id>/clear/", ClearChatContentView.as_view(), name="chat-clear"),
    path("<int:chat_id>/read/", MarkChatAsReadView.as_view(), name="chat-mark-read"),
    path("<int:chat_id>/share-links/", ShareLinkListView.as_view(), name="share-link-list"),
    path("<int:chat_id>/share-links/<int:link_id>/", ShareLinkDetailView.as_view(), name="share-link-detail"),
    path("<int:chat_id>/transcribe/", TranscribeView.as_view(), name="chat-transcribe"),
    path("<int:chat_id>/export/pdf/", ChatExportPDFView.as_view(), name="chat-export-pdf"),
    path("<int:chat_id>/export/markdown/", ChatExportMarkdownView.as_view(), name="chat-export-markdown"),
    path("<int:chat_id>/manage/export/pdf/", ChatManageExportPDFView.as_view(), name="chat-manage-export-pdf"),
    path("<int:chat_id>/manage/export/markdown/", ChatManageExportMarkdownView.as_view(),
         name="chat-manage-export-markdown"),
]
