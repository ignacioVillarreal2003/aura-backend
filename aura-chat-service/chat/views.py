from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .services import ChatService, MessageService
from .serializers import (
    CreateChatSerializer, UpdateChatSerializer, ChatSerializer,
    ChatSummarySerializer, SendMessageSerializer, ChatMessageSerializer,
)

chat_service = ChatService()
message_service = MessageService()


class ChatListView(APIView):
    def get(self, request):
        limit = min(int(request.query_params.get('limit', settings.DEFAULT_PAGE_SIZE)), settings.MAX_PAGE_SIZE)
        chats = chat_service.list_chats(request.user.id, limit)
        data = ChatSummarySerializer(chats, many=True).data
        return Response({
            'data': data,
            'pagination': {'has_more': False, 'next_cursor': None, 'total_count': len(data)},
        })

    def post(self, request):
        serializer = CreateChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chat = chat_service.create_chat(serializer.validated_data, request.user.id)
        return Response(ChatSerializer(chat).data, status=status.HTTP_201_CREATED)


class ChatDetailView(APIView):
    def get(self, request, chat_id):
        chat = chat_service.get_chat(chat_id, request.user.id)
        return Response(ChatSerializer(chat).data)

    def patch(self, request, chat_id):
        serializer = UpdateChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chat = chat_service.update_chat(chat_id, serializer.validated_data, request.user.id)
        return Response(ChatSerializer(chat).data)

    def delete(self, request, chat_id):
        chat_service.delete_chat(chat_id, request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageListView(APIView):
    def get(self, request, chat_id):
        limit = min(
            int(request.query_params.get('limit', 50)),
            settings.MAX_MESSAGES_PAGE_SIZE,
        )
        include_deleted = request.query_params.get('include_deleted', 'false').lower() == 'true'
        messages = message_service.list_messages(chat_id, request.user.id, limit, include_deleted)
        data = ChatMessageSerializer(messages, many=True).data
        return Response({
            'data': data,
            'pagination': {'has_more': False, 'next_cursor': None, 'total_count': len(data)},
        })

    def post(self, request, chat_id):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = getattr(request, 'bearer_token', 'user_token_123')
        reply = message_service.send_message(
            chat_id,
            serializer.validated_data['message'],
            request.user.id,
            token,
        )
        return Response(ChatMessageSerializer(reply).data, status=status.HTTP_201_CREATED)


class MessageDetailView(APIView):
    def get(self, request, chat_id, message_id):
        msg = message_service.get_message(chat_id, message_id, request.user.id)
        return Response(ChatMessageSerializer(msg).data)

    def delete(self, request, chat_id, message_id):
        message_service.delete_message(chat_id, message_id, request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
