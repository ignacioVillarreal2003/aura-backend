# Tiempo real — Server-Sent Events

Vista: `apps/notification/api/views/stream_view.py`  
Pub/sub: `core/pubsub/redis_pubsub.py`

---

## `GET /api/v1/notifications/stream/`

**Permiso:** `NOTIFICATION_STREAM_SUBSCRIBE`  
**Autenticación:** igual que el resto de la API de usuario (Bearer JWT o service key con usuario).

Abre una conexión HTTP larga con respuesta `text/event-stream`. El servidor envía frames SSE cada vez que hay un cambio relevante para el usuario autenticado, y heartbeats periódicos para mantener la conexión viva.

### Cabeceras de la respuesta

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache, no-transform
X-Accel-Buffering: no
```

`X-Accel-Buffering: no` le indica a nginx que no acumule el stream antes de enviarlo al cliente.

---

## Formato de los frames SSE

Cada evento sigue el formato estándar SSE:

```
event: notification.created
data: {"id": 123, "message": "Te invitaron al chat Proyecto X", "type": "event", ...}

```

Si el JSON ocupa varias líneas, cada línea va precedida por `data:`:

```
event: notification.updated
data: {"id": 123,
data:  "status": "read"}

```

Los heartbeats son comentarios SSE (el cliente los ignora automáticamente):

```
: keepalive

```

---

## Eventos que puede recibir el cliente

| Evento SSE | Cuándo se emite | Contenido del `data` |
| ---------- | --------------- | --------------------- |
| `stream.opened` | Al establecer la conexión | `{ "user_id": <id> }` |
| `notification.created` | Nueva notificación in-app para el usuario | Objeto completo de la notificación |
| `notification.updated` | Estado de una notificación cambiado por el usuario | `{ "id": <id>, "status": "<nuevo>" }` o `{ "all_marked_read": true, "until_id": <id|null>, "count": <n> }` |
| `notification.deleted` | Soft-delete de una notificación | `{ "id": <id> }` |
| `stream.closed` | El servidor cerró el stream (timeout de duración máxima) | `{ "reason": "max_duration" }` |
| `stream.error` | Error interno antes de cerrar | `{ "detail": "internal_error" }` |

> Si un mensaje de Redis llega sin campo `event`, el nombre del frame SSE será `notification.update` (sin "d" final). En la práctica no debería ocurrir con el publicador actual.

---

## Ciclo de vida del stream

1. El cliente abre la conexión → recibe `stream.opened`.
2. El servidor queda suscrito al canal Redis del usuario (`notif:user:<user_id>` por defecto).
3. Cada vez que otra parte del sistema llama a `realtime_service.publish_*`, el mensaje llega por Redis y se convierte en un frame SSE.
4. Cada `NOTIFICATION_SSE_HEARTBEAT_SECONDS` (por defecto **15 s**) sin mensajes, el servidor envía `: keepalive`.
5. Tras `NOTIFICATION_SSE_MAX_DURATION_SECONDS` (por defecto **1800 s = 30 min**), el servidor emite `stream.closed` y cierra la conexión. El cliente debe abrir una nueva.
6. Si el cliente cierra la conexión (navega, cierra la pestaña), el servidor lo detecta por `GeneratorExit` y limpia la suscripción Redis.

---

## Integración en el frontend

### Con `EventSource` (navegador)

```javascript
const es = new EventSource('/api/v1/notifications/stream/', {
  // EventSource no permite headers personalizados; usar cookies de sesión
  // o un proxy que inyecte el Authorization header
});

es.addEventListener('notification.created', (e) => {
  const notif = JSON.parse(e.data);
  // agregar notif al estado de la UI
});

es.addEventListener('notification.updated', (e) => {
  const update = JSON.parse(e.data);
  // actualizar notificación existente o recargar bandeja
});

es.addEventListener('notification.deleted', (e) => {
  const { id } = JSON.parse(e.data);
  // remover de la UI
});

es.addEventListener('stream.closed', () => {
  es.close();
  // reconectar después de un breve delay
});

es.onerror = () => {
  // el navegador reintenta automáticamente con EventSource
};
```

### Con `fetch` (para enviar Authorization header)

```javascript
const response = await fetch('/api/v1/notifications/stream/', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const reader = response.body.getReader();
// leer línea a línea y parsear el protocolo SSE manualmente
```

### Consideraciones

- **Sin SSE abierta**: las notificaciones **siguen persistidas** en la base de datos. Al cargar la app o volver de background, usar `GET /api/v1/notifications/` como fuente de verdad.
- **Múltiples pestañas**: cada pestaña crea una conexión independiente y una suscripción Redis separada.
- **Email vs SSE**: el correo va por un camino completamente distinto (RabbitMQ → Celery → SMTP) y **no pasa por el stream SSE**.
- **`EventSource` reconecta automáticamente** ante errores de red. Después de un `stream.closed` hay que reconectar manualmente.

---

## Variables de entorno relacionadas

| Variable | Por defecto | Descripción |
| -------- | ----------- | ----------- |
| `NOTIFICATION_SSE_HEARTBEAT_SECONDS` | `15` | Segundos entre heartbeats |
| `NOTIFICATION_SSE_MAX_DURATION_SECONDS` | `1800` | Duración máxima de una conexión SSE |
| `NOTIFICATION_REDIS_CHANNEL_PREFIX` | `notif:user` | Prefijo del canal Redis por usuario |
