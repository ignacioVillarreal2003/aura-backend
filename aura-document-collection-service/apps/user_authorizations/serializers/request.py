from rest_framework import serializers


class SetUserClearanceRequest(serializers.Serializer):
    classification_level_id = serializers.IntegerField(min_value=1)


class AddUserCompartmentRequest(serializers.Serializer):
    compartment_id = serializers.IntegerField(min_value=1)
