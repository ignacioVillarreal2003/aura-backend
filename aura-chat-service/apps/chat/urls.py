from django.urls import path

from apps.chat.views.chat_view import ChatViewSet
from apps.chat.views.share_link_view import ShareLinkDetailView, ShareLinkListView

_v = ChatViewSet

urlpatterns = [
    path("", _v.as_view({"get": "list", "post": "create"}), name="chat-list"),
    path("manage/", _v.as_view({"get": "manage"}), name="chat-manage"),
    path("me/", _v.as_view({"get": "my_chats"}), name="chat-me"),
    path("archived/", _v.as_view({"get": "archived"}), name="chat-archived"),
    path("archive/", _v.as_view({"post": "archive"}), name="chat-archive"),
    path("unarchive/", _v.as_view({"post": "unarchive"}), name="chat-unarchive"),
    path("<int:chat_id>/", _v.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
         name="chat-detail"),
    path("<int:chat_id>/pin/", _v.as_view({"post": "pin", "delete": "pin"}), name="chat-pin"),
    path("<int:chat_id>/lock/", _v.as_view({"post": "lock", "delete": "lock"}), name="chat-lock"),
    path("<int:chat_id>/mute/", _v.as_view({"post": "mute", "delete": "mute"}), name="chat-mute"),
    path("<int:chat_id>/share-links/", ShareLinkListView.as_view(), name="share-link-list"),
    path("<int:chat_id>/share-links/<int:link_id>/", ShareLinkDetailView.as_view(), name="share-link-detail"),
]
