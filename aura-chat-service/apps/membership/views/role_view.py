from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.membership.serializers.request import UpdateRoleRequest
from apps.membership.serializers.response import MembershipResponse
from apps.membership.services.membership_service import membership_service
from core.openapi.common import standard_error_responses


class RoleUpdateView(APIView):
    @extend_schema(
        tags=["Memberships"],
        summary="Update member role",
        description="Changes **owner / editor / reader** (or equivalent) for a member; subject to hierarchy rules in the service.",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="member_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        request=UpdateRoleRequest,
        responses={200: MembershipResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def patch(self, request: Request, chat_id: int, member_id: int) -> Response:
        serializer = UpdateRoleRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = membership_service.update_member_role(
            user=request.user,
            chat_id=chat_id,
            member_id=member_id,
            role=serializer.validated_data["role"],
        )
        return Response(MembershipResponse(membership).data)
