from rest_framework.views import exception_handler
from rest_framework.response import Response


class AppError(Exception):
    message = 'An error occurred'
    code = 'INTERNAL_ERROR'
    status_code = 500

    def __init__(self, message=None, details=None):
        super().__init__(message or self.message)
        if message:
            self.message = message
        self.details = details


class ConversationNotFoundError(AppError):
    message = 'Conversation not found'
    code = 'CONVERSATION_NOT_FOUND'
    status_code = 404


class MessageNotFoundError(AppError):
    message = 'Message not found'
    code = 'MESSAGE_NOT_FOUND'
    status_code = 404


class ForbiddenError(AppError):
    message = 'Access denied'
    code = 'FORBIDDEN'
    status_code = 403


class LLMError(AppError):
    message = 'Error communicating with LLM service'
    code = 'LLM_ERROR'
    status_code = 502


def custom_exception_handler(exc, context):
    if isinstance(exc, AppError):
        data = {'error': exc.code, 'message': exc.message}
        if exc.details:
            data['details'] = exc.details
        return Response(data, status=exc.status_code)

    return exception_handler(exc, context)
