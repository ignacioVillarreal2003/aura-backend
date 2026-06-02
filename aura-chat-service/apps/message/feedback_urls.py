from django.urls import path

from apps.message.views.feedback_analytics_view import FeedbackAnalyticsView

urlpatterns = [
    path("analytics/", FeedbackAnalyticsView.as_view(), name="feedback-analytics"),
]
