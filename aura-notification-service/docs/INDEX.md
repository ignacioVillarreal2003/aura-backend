# Índice de documentación — Aura Notification Service

Prefijo base de la API: **`/api/v1/`**  
Contrato OpenAPI en vivo: `/api/schema/` · Swagger: `/api/docs/` · ReDoc: `/api/redoc/`

| Documento | Qué cubre |
| --------- | --------- |
| [README.md](./README.md) | Visión general, arquitectura, flujo de una notificación de punta a punta |
| [api-autenticacion-y-errores.md](./api-autenticacion-y-errores.md) | Los tres métodos de auth, orden de evaluación, formato de errores, throttling |
| [api-bandeja-in-app.md](./api-bandeja-in-app.md) | Todos los endpoints de bandeja: listado, detalle, estados, borrado, mark-all-read |
| [api-preferencias.md](./api-preferencias.md) | Preferencias globales (in-app, email, mute) |
| [api-tiempo-real-sse.md](./api-tiempo-real-sse.md) | Stream SSE, formato de frames, eventos posibles, guía de integración frontend |
| [api-interna-productores.md](./api-interna-productores.md) | `POST /api/v1/internal/events/`, campos, respuesta `outcomes`, tipos de evento disponibles |
| [api-publica-salud-openapi.md](./api-publica-salud-openapi.md) | Health check, catálogo público de eventos, rutas OpenAPI |
| [event-types.md](./event-types.md) | Catálogo completo de tipos de evento: channels por defecto, severity, silenciabilidad, context fields para links |
