class DocumentDownloadServiceException(Exception):
    pass


class DocumentDownloadNotFoundException(DocumentDownloadServiceException):
    pass


class DocumentDownloadInvalidRequestException(DocumentDownloadServiceException):
    pass


class DocumentDownloadStorageException(DocumentDownloadServiceException):
    pass


class DocumentDownloadNotReadyException(DocumentDownloadServiceException):
    pass
