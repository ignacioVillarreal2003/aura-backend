from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.membership.serializers.response import ChatMembershipCheckResponse
from apps.membership.services.membership_service import membership_service
from core.openapi.common import standard_error_responses


class InternalChatMembershipView(APIView):
    # Service-to-service hot path: skip the per-user HTTP throttle. The caller is
    # a trusted microservice (often sharing the service principal), so a per-user
    # rate bucket would be both wrong and a bottleneck on the authorization path.
    throttle_classes: list = []

    @extend_schema(
        tags=["Internal"],
        summary="Check chat membership (internal)",
        description=(
            "Internal service-to-service endpoint. Reports whether `user_id` belongs to "
            "`chat_id` and with which role (`owner` or `member`). The chat creator is an "
            "implicit `owner`.\n\n"
            "Returns **200** with `is_member: false` and `role: null` for a real non-member, "
            "and **404** only when the chat does not exist or has been deleted — so callers "
            "can tell 'not a member' apart from 'no such chat'.\n\n"
            "Authenticate by forwarding the user's bearer token (identity and permissions are "
            "derived from it). A user may check their own membership; checking another user "
            "requires `MANAGE_MEMBERS` (**403** otherwise)."
        ),
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="user_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={200: ChatMembershipCheckResponse, **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int, user_id: int) -> Response:
        result = membership_service.check_membership(
            caller=request.user,
            chat_id=chat_id,
            user_id=user_id,
        )
        return Response(ChatMembershipCheckResponse(result).data)
