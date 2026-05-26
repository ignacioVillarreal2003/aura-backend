# API pública: catálogo de eventos, health check y OpenAPI

Estas rutas no requieren ningún tipo de autenticación.

---

## `GET /api/v1/event-types/`

Vista: `EventTypeCatalogueView` en `apps/notification/api/views/event_type_views.py`

Devuelve el catálogo completo de tipos de evento soportados por el servicio. Útil para armar pantallas de configuración de preferencias sin necesitar un JWT.

### Respuesta `200`

```json
[
  {
    "event_type": "chat.member.invited",
    "type": "event",
    "severity": "info",
    "description": "Te invitaron a un chat.",
    "default_channels": ["inapp"],
    "available_channels": ["inapp", "email"],
    "is_silenceable": true
  },
  {
    "event_type": "auth.password.changed",
    "type": "system",
    "severity": "critical",
    "description": "Cambio de contrasena exitoso.",
    "default_channels": ["inapp", "email"],
    "available_channels": ["inapp", "email"],
    "is_silenceable": false
  }
]
```

| Campo | Descripción |
| ----- | ----------- |
| `event_type` | Identificador único del evento |
| `type` | Categoría: `system` · `admin` · `user` · `event` |
| `severity` | `info` · `success` · `warning` · `critical` |
| `description` | Texto descriptivo del evento |
| `default_channels` | Canales activos por defecto si el usuario no tiene override |
| `available_channels` | Canales que el usuario puede configurar |
| `is_silenceable` | Si `false`, el evento se entrega siempre ignorando preferencias del usuario |

---

## `GET /api/v1/health`

Vista: `health_check` en `apps/notification/api/views/health_view.py`

Verifica la conectividad con las tres dependencias críticas del servicio.

### Respuesta `200` — todo ok

```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "broker": "ok"
  }
}
```

### Respuesta `503` — alguna dependencia falla

```json
{
  "status": "degraded",
  "checks": {
    "database": "ok",
    "redis": "error",
    "broker": "ok"
  }
}
```

| Check | Qué verifica |
| ----- | ------------ |
| `database` | Conexión a Postgres (`connection.ensure_connection()`) |
| `redis` | Ping a `REDIS_URL` con timeout de 2 s |
| `broker` | Conexión a `CELERY_BROKER_URL` (RabbitMQ) con timeout de 2 s vía Kombu |

El código HTTP es **200** si todos los checks son `"ok"`, **503** si alguno falla. Los probes de Kubernetes o del balanceador deben distinguir estos dos códigos para marcar el pod como no disponible cuando el servicio esté degradado.

---

## Rutas OpenAPI

Definidas en `aura_notification_service/urls.py`. No llevan prefijo `/api/v1/`.

| Ruta | Descripción |
| ---- | ----------- |
| `GET /api/schema/` | Esquema OpenAPI en formato YAML/JSON (drf-spectacular) |
| `GET /api/docs/` | Swagger UI interactivo |
| `GET /api/redoc/` | ReDoc |

El título, versión, descripción y esquemas de seguridad del esquema OpenAPI se configuran en `SPECTACULAR_SETTINGS` dentro de `aura_notification_service/settings/base.py`.
