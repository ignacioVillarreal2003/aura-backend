import hashlib
import hmac
import json
import logging
import secrets
import threading

import requests
from django.db.transaction import on_commit

from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.models.webhook import WEBHOOK_EVENTS, ChatWebhook
from apps.chat.repositories.chat_repository import chat_repository
from apps.chat.repositories.webhook_repository import webhook_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import GET_CHAT
from core.exceptions import NotFoundException, ValidationException

logger = logging.getLogger(__name__)


class WebhookNotFoundException(NotFoundException):
    error_code = "webhook_not_found"
    detail = "Webhook not found"


def _sign_payload(secret: str, body: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def _dispatch(url: str, body: str, signature: str) -> None:
    try:
        requests.post(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": f"sha256={signature}",
            },
            timeout=5,
        )
    except Exception as exc:
        logger.warning("Webhook delivery failed for %s: %s", url, exc)


class WebhookService:
    def create_webhook(
        self,
        user: AuthenticatedUser,
        chat_id: int,
        url: str,
        events: list[str],
    ) -> ChatWebhook:
        AccessControl.require_permissions(user, frozenset({GET_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can manage webhooks")
        invalid = [e for e in events if e not in WEBHOOK_EVENTS]
        if invalid:
            raise ValidationException(
                detail=f"Invalid events: {', '.join(invalid)}. Allowed: {', '.join(WEBHOOK_EVENTS)}",
                error_code="invalid_webhook_events",
            )
        secret = secrets.token_hex(32)
        hook = webhook_repository.create(
            chat_id=chat_id,
            url=url,
            events=events,
            secret=secret,
            created_by=user.id,
        )
        logger.info("Webhook created.", extra={"chat_id": chat_id, "webhook_id": hook.id, "user_id": user.id})
        return hook

    def list_webhooks(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({GET_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can list webhooks")
        return webhook_repository.list_by_chat(chat_id)

    def update_webhook(
        self,
        user: AuthenticatedUser,
        chat_id: int,
        webhook_id: int,
        **fields,
    ) -> ChatWebhook:
        AccessControl.require_permissions(user, frozenset({GET_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can manage webhooks")
        hook = webhook_repository.get_by_id(webhook_id, chat_id)
        if hook is None:
            raise WebhookNotFoundException()
        if "events" in fields:
            invalid = [e for e in fields["events"] if e not in WEBHOOK_EVENTS]
            if invalid:
                raise ValidationException(
                    detail=f"Invalid events: {', '.join(invalid)}. Allowed: {', '.join(WEBHOOK_EVENTS)}",
                    error_code="invalid_webhook_events",
                )
        return webhook_repository.update(hook, **fields)

    def delete_webhook(self, user: AuthenticatedUser, chat_id: int, webhook_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({GET_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can manage webhooks")
        hook = webhook_repository.get_by_id(webhook_id, chat_id)
        if hook is None:
            raise WebhookNotFoundException()
        webhook_repository.delete(hook)
        logger.info("Webhook deleted.", extra={"chat_id": chat_id, "webhook_id": webhook_id, "user_id": user.id})

    @staticmethod
    def fire_event(chat_id: int, event: str, payload: dict) -> None:
        hooks = webhook_repository.list_active_by_chat_and_event(chat_id, event)
        if not hooks:
            return
        body = json.dumps({"event": event, "chat_id": chat_id, **payload}, default=str)
        for hook in hooks:
            _schedule_delivery(hook.url, hook.secret, body)


def _schedule_delivery(url: str, secret: str, body: str) -> None:
    sig = _sign_payload(secret, body)

    def _deliver():
        threading.Thread(target=_dispatch, args=(url, body, sig), daemon=True).start()

    on_commit(_deliver)


webhook_service = WebhookService()
