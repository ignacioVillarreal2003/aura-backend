from core.exceptions import ConflictException, ForbiddenException, NotFoundException


class MembershipNotFoundException(NotFoundException):
    error_code = "membership_not_found"
    detail = "Membership not found"


class MembershipAlreadyExistsException(ConflictException):
    error_code = "membership_already_exists"
    detail = "User is already a member of this chat"


class MembershipForbiddenException(ForbiddenException):
    error_code = "membership_forbidden"
    detail = "You do not have permission to manage members in this chat"


class CannotRemoveOwnerException(ForbiddenException):
    error_code = "cannot_remove_owner"
    detail = "The chat owner cannot be removed"


class RoleUpdateForbiddenException(ForbiddenException):
    error_code = "role_update_forbidden"
    detail = "Only the chat owner can update member roles"
