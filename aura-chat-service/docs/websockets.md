# WebSocket — chat en tiempo real

Complementa el **REST** (`/api/v1/…`) para envío de mensajes, indicadores de escritura, streaming de respuestas del asistente y eventos de sala vía **Channels** y un **Channel layer** (Redis).

## URL y handshake

- **Patrón** (definido en [apps/message/routing.py](../apps/message/routing.py)): `ws/chat/{chat_id}/`
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

Tipos no exhaustivos (ver [apps/message/consumers/chat_consumer.py](../apps/message/consumers/chat_consumer.py)):

| `type` | Rol |
|--------|-----|
| `chat_ai_lock` | Estado del candado global de generación IA (`locked` boolean). |
| `user_message` | Eco/confirmación relacionada con mensaje de usuario. |
| `ai_meta`, `ai_context`, `ai_delta`, `ai_complete`, `ai_error` | Metadatos, contexto, fragmentos stream, finalización o error de la respuesta del modelo. |
| `typing` | Otro usuario está escribiendo. |
| `chat_locked_changed` | Cambió el estado de bloqueo del chat. |
| `member_joined` / `member_left` | Presencia de miembros. |
| `error` | Errores genéricos o de negocio (`detail`, opcional `error_code`). |

Los códigos de error en payload pueden incluir p. ej. `chat_locked`, `message_too_long`, `rate_limit_exceeded`, `chat_ai_reply_in_progress`, etc.

## Permisos REST vs WebSocket

El consumidor **no** llama a `AccessControl.require_permissions` por cada string como en las vistas REST; exige **usuario válido** + **miembro activo** + reglas de negocio en tiempo real (bloqueo, rate limits, lock de IA). Las políticas de producto deben alinearse: un usuario sin acceso al chat no debe conectar o será cerrado con **4003**.

## Dónde cablear el ASGI

 [aura_chat_service/asgi.py](../aura_chat_service/asgi.py) monta `WebSocketAuthMiddleware` sobre `URLRouter(websocket_urlpatterns)` para el tráfico **websocket**.

Para detalle fino de cada payload, inspeccionar el consumidor; para contrato REST sigue siendo el OpenAPI en `/api/schema/`.
