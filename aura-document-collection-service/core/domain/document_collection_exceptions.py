from core.exceptions.base import ConflictException, NotFoundException


class CollectionNotFoundException(NotFoundException):
    def __init__(self):
        super().__init__(
            detail="Document collection not found",
            error_code="document_collection_not_found",
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


class DuplicateDocumentLinkException(ConflictException):
    def __init__(self):
        super().__init__(
            detail="Document is already linked to this document collection",
            error_code="duplicate_document_link",
        )


class ClassificationLevelNotFoundException(NotFoundException):
    def __init__(self):
        super().__init__(
            detail="Classification level not found",
            error_code="classification_level_not_found",
        )


class DuplicateClassificationLevelException(ConflictException):
    def __init__(self):
        super().__init__(
            detail="A classification level with this name or rank already exists",
            error_code="duplicate_classification_level",
        )


class ClassificationLevelInUseException(ConflictException):
    def __init__(self):
        super().__init__(
            detail="Classification level is in use and cannot be deleted",
            error_code="classification_level_in_use",
        )


class CompartmentNotFoundException(NotFoundException):
    def __init__(self):
        super().__init__(
            detail="Compartment not found",
            error_code="compartment_not_found",
        )


class DuplicateCompartmentException(ConflictException):
    def __init__(self):
        super().__init__(
            detail="A compartment with this name already exists",
            error_code="duplicate_compartment",
        )


class CompartmentInUseException(ConflictException):
    def __init__(self):
        super().__init__(
            detail="Compartment is in use and cannot be deleted",
            error_code="compartment_in_use",
        )


class UserClearanceNotFoundException(NotFoundException):
    def __init__(self):
        super().__init__(
            detail="User clearance not found",
            error_code="user_clearance_not_found",
        )


class DuplicateUserCompartmentException(ConflictException):
    def __init__(self):
        super().__init__(
            detail="User is already assigned to this compartment",
            error_code="duplicate_user_compartment",
        )


class UserCompartmentNotFoundException(NotFoundException):
    def __init__(self):
        super().__init__(
            detail="User compartment assignment not found",
            error_code="user_compartment_not_found",
        )
