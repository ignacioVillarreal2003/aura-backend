from rest_framework import serializers

from apps.classification_levels.models import ClassificationLevel


class ClassificationLevelResponse(serializers.ModelSerializer):
    class Meta:
        model = ClassificationLevel
        fields = ["id", "name", "rank"]
