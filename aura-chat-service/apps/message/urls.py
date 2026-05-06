from django.urls import path

from apps.message.views.bookmark_view import BookmarkedMessageListView, BookmarkView
from apps.message.views.clear_view import ClearHistoryView
from apps.message.views.export_view import (
    AIResponsesExportView,
    ChatExportJSONView,
    ChatExportMarkdownView,
    ChatExportPDFView,
    MessageExportPDFView,
)
from apps.message.views.feedback_view import FeedbackView
from apps.message.views.mark_read_view import MarkAsReadView
from apps.message.views.message_delete_view import MessageDeleteView
from apps.message.views.message_view import MessageListView
from apps.message.views.pin_view import PinMessageView, PinnedMessageListView
from apps.message.views.regenerate_view import RegenerateResponseView
from apps.message.views.thread_view import ThreadView

urlpatterns = [
    path("", MessageListView.as_view(), name="message-list"),
    path("clear/", ClearHistoryView.as_view(), name="message-clear"),
    path("read/", MarkAsReadView.as_view(), name="message-mark-read"),
    path("pinned/", PinnedMessageListView.as_view(), name="message-pinned-list"),
    path("regenerate/", RegenerateResponseView.as_view(), name="message-regenerate"),
    path("bookmarked/", BookmarkedMessageListView.as_view(), name="message-bookmarked"),
    path("export/pdf/", ChatExportPDFView.as_view(), name="chat-export-pdf"),
    path("export/markdown/", ChatExportMarkdownView.as_view(), name="chat-export-markdown"),
    path("export/json/", ChatExportJSONView.as_view(), name="chat-export-json"),
    path("export/ai/", AIResponsesExportView.as_view(), name="chat-export-ai"),
    path("<int:message_id>/", MessageDeleteView.as_view(), name="message-delete"),
    path("<int:message_id>/bookmark/", BookmarkView.as_view(), name="message-bookmark"),
    path("<int:message_id>/pin/", PinMessageView.as_view(), name="message-pin"),
    path("<int:message_id>/thread/", ThreadView.as_view(), name="message-thread"),
    path("<int:message_id>/feedback/", FeedbackView.as_view(), name="message-feedback"),
    path("<int:message_id>/export/pdf/", MessageExportPDFView.as_view(), name="message-export-pdf"),
]
