from core.exceptions.base import ConflictException, NotFoundException


class CollectionNotFoundException(NotFoundException):
    def __init__(self):
        super().__init__(
            detail="Document collection not found",
            error_code="document_collection_not_found",
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
