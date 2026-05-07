from __future__ import annotations

from rest_framework import serializers

from apps.classification_levels.serializers.response import ClassificationLevelResponse
from apps.compartments.serializers.response import CompartmentResponse
from apps.user_authorizations.models import UserClearance, UserCompartment


class UserClearanceResponse(serializers.ModelSerializer):
    classification_level = ClassificationLevelResponse(read_only=True)

    class Meta:
        model = UserClearance
        fields = ["id", "user_id", "classification_level", "created_by", "created_at"]


class UserCompartmentResponse(serializers.ModelSerializer):
    compartment = CompartmentResponse(read_only=True)

    class Meta:
        model = UserCompartment
        fields = ["id", "user_id", "compartment", "created_by", "created_at"]


class UserAuthorizationResponse(serializers.Serializer):
    user_id = serializers.IntegerField()
    clearance = UserClearanceResponse(allow_null=True)
    compartments = UserCompartmentResponse(many=True)
