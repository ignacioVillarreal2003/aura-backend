from core.exceptions.base import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)


class CollectionNotFoundException(NotFoundException):
    def __init__(self):
        super().__init__(
            detail="Document collection not found",
            error_code="document_collection_not_found",
        )


class CollectionAccessDeniedException(ForbiddenException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            detail=detail or "You are not a member of this document collection",
            error_code="document_collection_access_denied",
        )


class CollectionOwnerRequiredException(ForbiddenException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            detail=detail or "Only the document collection owner can perform this action",
            error_code="document_collection_owner_required",
        )


class UserMembershipNotFoundException(NotFoundException):
    def __init__(self):
        super().__init__(
            detail="User membership not found",
            error_code="user_membership_not_found",
        )


class DocumentLinkNotFoundException(NotFoundException):
    def __init__(self):
        super().__init__(
            detail="Document link not found",
            error_code="document_link_not_found",
        )


class CannotRemoveOwnerException(ForbiddenException):
    def __init__(self):
        super().__init__(
            detail="Cannot remove the document collection owner from the document collection",
            error_code="cannot_remove_owner",
        )


class OwnerCannotLeaveException(ForbiddenException):
    def __init__(self):
        super().__init__(
            detail="Document collection owner cannot leave; delete the document collection or transfer ownership",
            error_code="owner_cannot_leave",
        )


class DocumentNotAvailableException(NotFoundException):
    def __init__(self):
        super().__init__(
            detail="Document not found or has been deleted",
            error_code="document_not_available",
        )


class DuplicateMembershipException(ConflictException):
    def __init__(self):
        super().__init__(
            detail="User is already in this document collection",
            error_code="duplicate_membership",
        )


class DuplicateDocumentLinkException(ConflictException):
    def __init__(self):
        super().__init__(
            detail="Document is already linked to this document collection",
            error_code="duplicate_document_link",
        )
