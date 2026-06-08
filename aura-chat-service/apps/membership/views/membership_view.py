from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.membership.models.chat_membership import ChatMembership
from apps.membership.serializers.request import AddMemberRequest, UpdateMemberRequest
from apps.membership.serializers.response import MembershipResponse
from apps.membership.services.membership_service import membership_service
from core.exceptions import ValidationException
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

_STATUS_CHOICES = [*ChatMembership.Status.values, "all"]
_MY_STATUS_CHOICES = ChatMembership.Status.values


class MemberListView(APIView):
    @extend_schema(
        tags=["Memberships"],
        summary="List members",
        description=(
                "Paginated membership rows for the chat. Optional `status` query: membership status or `all`. "
                "Invalid values return **400** with a structured error (not the standard DRF validation shape)."
        ),
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=_STATUS_CHOICES,
                description='Filter by membership status. Defaults to "active". Use "all" to return every status.',
            ),
        ],
        responses={200: MembershipResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
        raw_status = request.query_params.get("status", "active")
        if raw_status not in _STATUS_CHOICES:
            raise ValidationException(
                detail=f"Invalid status '{raw_status}'. Allowed: {', '.join(_STATUS_CHOICES)}.",
                error_code="invalid_status",
            )
        status_filter = None if raw_status == "all" else raw_status
        members = membership_service.list_members(
            user=request.user,
            chat_id=chat_id,
            status=status_filter,
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(members, request)
        return paginator.get_paginated_response(
            MembershipResponse(page, many=True).data
        )

    @extend_schema(
        tags=["Memberships"],
        summary="Invite members",
        description=(
                "Adds users by id list (deduplicated). **Owner only** — only the chat owner can invite members. "
                "Invited members are created with `status: pending` and must accept the invitation themselves. "
                "The service may notify downstream systems using the same Bearer token from the `Authorization` header. "
                "**409** if a member already exists or state conflicts."
        ),
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        request=AddMemberRequest,
        responses={201: MembershipResponse(many=True), **standard_error_responses(400, 401, 403, 404, 409)},
    )
    def post(self, request: Request, chat_id: int) -> Response:
        serializer = AddMemberRequest(data=request.data)
        serializer.is_valid(raise_exception=True)

        memberships = membership_service.add_members(
            user=request.user,
            chat_id=chat_id,
            member_ids=serializer.validated_data["member_ids"],
        )
        return Response(
            MembershipResponse(memberships, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class AdminMemberListView(APIView):
    @extend_schema(
        tags=["Memberships"],
        summary="List members (admin)",
        description=(
                "Admin view: lists membership rows for any chat without requiring chat membership. "
                "Requires `MANAGE_MEMBERS`. Defaults to returning all statuses; use `status` to filter."
        ),
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=_STATUS_CHOICES,
                description='Filter by membership status. Omit to return every status. Use "all" explicitly for the same effect.',
            ),
        ],
        responses={200: MembershipResponse(many=True), **standard_error_responses(400, 401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
        raw_status = request.query_params.get("status") or None
        if raw_status is not None and raw_status not in _STATUS_CHOICES:
            raise ValidationException(
                detail=f"Invalid status '{raw_status}'. Allowed: {', '.join(_STATUS_CHOICES)}.",
                error_code="invalid_status",
            )
        status_filter = None if (raw_status is None or raw_status == "all") else raw_status
        members = membership_service.list_members_admin(
            user=request.user,
            chat_id=chat_id,
            status=status_filter,
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(members, request)
        return paginator.get_paginated_response(
            MembershipResponse(page, many=True).data
        )


class MemberDetailView(APIView):
    @extend_schema(
        tags=["Memberships"],
        summary="Update member status",
        description=(
                "Accepts a pending invitation by transitioning the authenticated user's own membership "
                "`pending → active`. This is the only valid status transition. **Only the invited member can "
                "change their own status** — the chat owner cannot override this on behalf of another user. "
                "To leave or decline, use **Leave chat**."
        ),
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="member_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        request=UpdateMemberRequest,
        responses={200: MembershipResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def patch(self, request: Request, chat_id: int, member_id: int) -> Response:
        serializer = UpdateMemberRequest(data=request.data)
        serializer.is_valid(raise_exception=True)

        membership = membership_service.update_member(
            user=request.user,
            chat_id=chat_id,
            member_id=member_id,
            new_status=serializer.validated_data["status"],
        )
        return Response(MembershipResponse(membership).data)

    @extend_schema(
        tags=["Memberships"],
        summary="Remove member",
        description="Removes another user from the chat (not self-serve leave; use **Leave chat** for that).",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="member_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, chat_id: int, member_id: int) -> Response:
        membership_service.remove_member(
            user=request.user,
            chat_id=chat_id,
            member_id=member_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyMembershipsView(APIView):
    @extend_schema(
        tags=["Memberships"],
        summary="List my memberships",
        description=(
                "Returns all memberships for the authenticated user across every chat. "
                "Use `status=pending` to see pending invitations that have not been accepted or declined yet."
        ),
        parameters=[
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=_MY_STATUS_CHOICES,
                description="Filter by membership status. Omit to return all statuses.",
            ),
        ],
        responses={200: MembershipResponse(many=True), **standard_error_responses(401)},
    )
    def get(self, request: Request) -> Response:
        raw_status = request.query_params.get("status") or None
        if raw_status is not None and raw_status not in _MY_STATUS_CHOICES:
            raise ValidationException(
                detail=f"Invalid status '{raw_status}'. Allowed: {', '.join(_MY_STATUS_CHOICES)}.",
                error_code="invalid_status",
            )
        memberships = membership_service.list_my_memberships(user=request.user, status=raw_status)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(memberships, request)
        return paginator.get_paginated_response(MembershipResponse(page, many=True).data)


class LeaveChatView(APIView):
    http_method_names = ["post"]

    @extend_schema(
        tags=["Memberships"],
        summary="Leave chat",
        description="The authenticated user leaves this chat (membership updated accordingly).",
        request=None,
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    def post(self, request: Request, chat_id: int) -> Response:
        membership_service.leave_chat(user=request.user, chat_id=chat_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
