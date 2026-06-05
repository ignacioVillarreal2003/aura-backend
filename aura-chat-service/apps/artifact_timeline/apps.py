from django.apps import AppConfig


class TimelineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.artifact_timeline"
    label = "timeline"
