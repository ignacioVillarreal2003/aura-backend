# WebSocket — chat en tiempo real

Complementa el **REST** (`/api/v1/…`) para envío de mensajes, indicadores de escritura, streaming de respuestas del asistente y eventos de sala vía **Channels** y un **Channel layer** (Redis).

## URL y handshake

- **Patrón** (definido en [apps/chat/routing.py](../apps/chat/routing.py)): `ws/chat/{chat_id}/`
- Tras el despliegue, la URL completa depende del host y de si usas TLS (`wss://`). Ejemplo:

  `wss://<host>/ws/chat/42/?token=<JWT>`

## Autenticación

- El middleware [core/authentication/websocket_auth_middleware.py](../core/authentication/websocket_auth_middleware.py) exige el **token JWT en query string**: **`?token=...`**
- Sin `token`: cierre del socket con código **4001**.
- Token inválido o error al validar con el proveedor: cierre **4003**.
- Tras autenticar, el consumidor comprueba **membresía activa** en el chat; si no es miembro, cierra con **4003**.

No se usa el header `Authorization` en el upgrade WebSocket estándar de la misma forma que en REST; el cliente debe pasar el token en la query.

## Mensajes entrantes (cliente → servidor)

JSON con campo **`type`**:

| `type` | Descripción |
|--------|-------------|
| `chat.message` | Envía texto de usuario; campo típico `message` (string). Respeta bloqueo del chat, longitud máxima, rate limit y lock de “IA ocupada”. Dispara persistencia y flujo de respuesta del asistente (vía `message_service`). |
| `chat.typing` | Indica actividad de escritura; se reenvía a la sala con rate limit independiente. |

Cualquier otro `type` recibe un mensaje `{"type":"error","detail":"Unknown message type: …"}`.

## Mensajes salientes (servidor → cliente)

Tipos no exhaustivos (ver [apps/chat/consumers/chat_consumer.py](../apps/chat/consumers/chat_consumer.py)):

| `type` | Rol |
|--------|-----|
| `chat_ai_lock` | Estado del candado por-chat de generación IA (`locked` boolean). Una sola generación por chat; chats distintos generan en paralelo. |
| `user_message` | Eco/confirmación relacionada con mensaje de usuario (se emite a toda la sala). |
| `ai_meta`, `ai_context`, `ai_progress`, `ai_delta`, `ai_complete`, `ai_error` | Metadatos, contexto, progreso, fragmentos stream, finalización o error de la respuesta del modelo (se emite a toda la sala). |
| `typing` | Otro usuario está escribiendo. |
| `chat_locked_changed` | Cambió el estado de bloqueo del chat. |
| `member_joined` / `member_left` | **Membresía**: alta (al aceptar invitación) / baja (removido o salida). |
| `presence_joined` / `presence_left` | **Presencia** (conteo de referencias por usuario): el usuario abrió su primera conexión / cerró su última. Cerrar una de varias pestañas **no** emite `presence_left`. |
| `membership_revoked` | El receptor perdió acceso (removido / dejó el chat). Su propio socket se cierra (código **4003**). |
| `chat_content_cleared` | El dueño limpió el historial: el cliente debe vaciar mensajes y artefactos. |
| `chat_deleted` | El chat fue eliminado; el socket se cierra (código **4004**). |
| `artifact_created` / `artifact_deleted` | Un artefacto fue creado / eliminado en el chat (visible para todos). Los artefactos son inmutables: no hay evento de actualización. |
| `error` | Errores genéricos o de negocio (`detail`, opcional `error_code`). |

Los códigos de error en payload pueden incluir p. ej. `chat_not_found`, `chat_locked`, `not_a_member`, `reader_cannot_send`, `message_too_long`, `rate_limit_exceeded`, `chat_ai_reply_in_progress`, etc.

Códigos de cierre adicionales: **4004** (`chat_deleted`), **4029** (demasiadas conexiones concurrentes del usuario).

## Permisos REST vs WebSocket

El consumidor **no** llama a `AccessControl.require_permissions` por cada string como en las vistas REST; exige **usuario válido** + **miembro activo** + reglas de negocio en tiempo real (bloqueo, rate limits, lock de IA). Las políticas de producto deben alinearse: un usuario sin acceso al chat no debe conectar o será cerrado con **4003**.

## Dónde cablear el ASGI

 [aura_chat_service/asgi.py](../aura_chat_service/asgi.py) monta `WebSocketAuthMiddleware` sobre `URLRouter(websocket_urlpatterns)` para el tráfico **websocket**.

Para detalle fino de cada payload, inspeccionar el consumidor; para contrato REST sigue siendo el OpenAPI en `/api/schema/`.
