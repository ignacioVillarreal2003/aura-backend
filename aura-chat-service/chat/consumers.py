import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from jose import jwt, JWTError

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = int(self.scope['url_route']['kwargs']['chat_id'])
        token = self._get_token()
        self.user_id = self._decode_token(token)
        self.bearer_token = token or 'user_token_123'

        await self.accept()
        logger.info(f'WebSocket connected: chat={self.chat_id}, user={self.user_id}')

    async def disconnect(self, close_code):
        logger.info(f'WebSocket disconnected: chat={self.chat_id}, user={self.user_id}')

    async def receive(self, text_data):
        from .services import MessageService
        from .exceptions import ForbiddenError, ConversationNotFoundError, LLMError

        try:
            data = json.loads(text_data)
            message_text = data.get('message', '').strip()

            if not message_text:
                await self._send_error('EMPTY_MESSAGE', 'Message cannot be empty')
                return

            service = MessageService()
            reply = await database_sync_to_async(service.send_message)(
                self.chat_id, message_text, self.user_id, self.bearer_token
            )

            await self.send(text_data=json.dumps({
                'type': 'message',
                'data': {
                    'id': reply.id,
                    'chat_id': reply.chat_id,
                    'message': reply.message,
                    'sender_type': reply.sender_type,
                    'created_by': reply.created_by,
                    'created_at': reply.created_at.isoformat(),
                },
            }))

        except ForbiddenError:
            await self._send_error('FORBIDDEN', 'User is not a member of this chat')
        except ConversationNotFoundError:
            await self._send_error('NOT_FOUND', 'Chat not found')
        except LLMError as e:
            await self._send_error('LLM_ERROR', str(e))
        except Exception:
            logger.exception('Unhandled WebSocket error')
            await self._send_error('INTERNAL_ERROR', 'An unexpected error occurred')

    async def _send_error(self, code, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'code': code,
            'message': message,
        }))

    def _get_token(self):
        query_string = self.scope.get('query_string', b'').decode()
        for param in query_string.split('&'):
            if param.startswith('token='):
                return param[6:]
        return None

    def _decode_token(self, token):
        if not token:
            return 1
        from django.conf import settings
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            return payload.get('user_id') or int(payload.get('sub', 1))
        except JWTError:
            return 1
