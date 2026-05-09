from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notification.api.serializers import EventTypeCatalogueEntrySerializer
from apps.notification.events import iter_events


@extend_schema(tags=["Event Types"])
class EventTypeCatalogueView(APIView):
    """Read-only public catalogue. Used by the frontend to render the
    notification preferences screen without hard-coding event metadata."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="List notification event types",
        auth=[],
        responses={200: EventTypeCatalogueEntrySerializer(many=True)},
    )
    def get(self, request):
        return Response([event.to_public_dict() for event in iter_events()])
