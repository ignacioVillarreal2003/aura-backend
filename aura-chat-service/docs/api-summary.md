# Visión general: qué hace la API y cómo encajan los datos

Este documento es una **lectura humana** del servicio: propósito, piezas principales del modelo de datos y flujos habituales. Para rutas HTTP exactas usa [endpoints.md](endpoints.md); para errores [errors-and-status-codes.md](errors-and-status-codes.md); para autenticación y permisos [permissions.md](permissions.md); para mensajería en tiempo real [websockets.md](websockets.md).

---

## 1. Propósito del servicio en el conjunto Aura

Este microservicio responde a una familia de preguntas centrada en **conversaciones colaborativas con IA y personas**:

**¿Qué chats existen, quién puede verlos y con qué rol, cómo evoluciona el historial de mensajes, y qué mecanismos hay para compartir de solo lectura, notificar sistemas externos o exportar contenido?**

No sustituye al **servicio de identidad/autenticación** que firma JWT ni al catálogo **MAC / colecciones de documentos** de otros dominios; aquí viven el **chat** (metadatos, etiquetas, bloqueo global), las **membresías** (rol, estado, preferencias por usuario como fijación, archivo, silencio o cursor de lectura), el **mensaje** como línea persistida (`chat_message`) y artefactos de producto (**enlaces públicos**, **webhooks**, **hilos**, **marcadores**, **pins**, **feedback**). El envío típico de mensajes para la experiencia conversacional suele hacerse también por **WebSocket** ([websockets.md](websockets.md)), mientras que la API REST lista, borra, exporta y orquesta el ciclo de vida del chat.

---

## 2. Conceptos en lenguaje simple (sin jerga innecesaria)

- **Chat** (`chat`): contenedor nombrado con prompts y estilo de respuesta opcionales, etiquetas (`tags`), flag **`is_ephemeral`** (historial/flujo efímero según reglas de producto), **`is_locked`** (nadie puede enviar mientras está bloqueado) y auditoría con **borrado lógico** en soft delete del núcleo.
- **Membresía** (`chat_membership`): relaciona un **usuario del ecosistema** (`member_id` numérico) con un chat. Incluye **rol** (`owner`, `editor`, `reader`), **estado** (`active`, `inactive`, `pending`) y timestamps de producto (**unión**, **silencio hasta**, **pin personal**, **archivo personal**, **último leído**, etc.).
- **Mensaje** (`chat_message`): fila del historial con texto, tipo de remitente (usuario vs sistema), FK al chat y soft delete para conservar auditoría donde aplique.

En conjunto: *quién tiene acceso*, *con qué capacidad*, *qué texto se registró*, más *preferencias por usuario sobre la misma conversación* (pin, archivo, mute, leídos).

---

## 3. ¿Quién hace qué? (roles de negocio, no tablas Django)

Aquí hablamos de **roles de producto**. En la práctica son cuentas o servicios cuyo usuario autenticado trae **permisos** (strings como `CREATE_CHAT`, `SEND_MESSAGE`); la lista completa está en [permissions.md](permissions.md).

| Rol conceptual | Ejemplos de acciones |
|----------------|---------------------|
| **Creador / propietario de chat** | Crear chats, cerrar temporalmente la conversación con **lock/unlock**, invitar miembros, gestionar enlaces públicos y webhooks si tiene permiso. |
| **Colaborador (editor)** | Ver mensajes, enviar contenido (**WS** habitualmente para envío fluido), marcar lectura, participar en hilos, usar exportaciones permitidas. |
| **Lector** | Consumir historia y vistas de solo lectura según política del producto sobre ese rol. |
| **Administración de integraciones** | Configurar **webhooks** para eventos (`message.created`, miembros, lock…). |
| **Compartición pública** | Acceder a **mensajes vía token** en la ruta pública de share (`/api/v1/share/...`) sin reproducir todo el modelo de membresía; el contrato detallado está en [api-overview.md](api-overview.md) y [endpoints.md](endpoints.md). |

No hay “mesa de admins” dentro de esta API más allá del conjunto de permisos efectivo que trae cada usuario.

---

## 4. Tablas (o equivalentes) y para qué existen

Los modelos están **gestionados por Django salvo donde se note lo contrario**; los nombres de tabla siguen la intención de negocio.

| Concepto | Tabla / idea | Propósito |
|----------|----------------|-----------|
| Conversación | `chat` | Núcleo: nombre, prompts, tags, ephemeral, locked, orden temporal de actividad. |
| Pertenencia y preferencias por usuario | `chat_membership` | Rol, estado, pin/archivo/mute/leídos personales sobre el mismo chat. |
| Mensaje | `chat_message` | Histórico de texto y remitente; base para listados REST, hilos y exportación. |
| Enlace de solo lectura | `chat_share_link` | UUID (`token`), expiración opcional, activación; permite rutas públicas acotadas. |
| Suscripción externa | `chat_webhook` | URL objetivo, `events` seleccionados, secreto para verificación típica de callbacks. |

Artefactos adicionales (bookmarks, pins de mensaje, feedback, respuestas de hilo…) enlazan desde el mensaje o el chat según correspondan — ver modelo en código y OpenAPI para campos exactos.

Orden mental: **chat** → **miembros** → **mensajes** y extensiones (**share**, **webhook**, hilos/export).

---

## 5. Flujos típicos (de punta a punta)

### 5.1 Crear y descubrir conversaciones

1. Con `CREATE_CHAT` se hace **POST** a **`/api/v1/chats/`** con nombre opcionalmente enriquecido por prompts/tags/ephemeral ([endpoints.md](endpoints.md)).
2. **`GET .../chats/`** lista la bandeja con filtros `search`, `ordering` y `tags` (deben coincidir **todas** las etiquetas pedidas). **`.../chats/me/`** acota a chats creados por el usuario.
3. **Archivado personal**: **POST** `.../chats/archive/` y `.../chats/unarchive/` con listas de ids; **GET** `.../chats/archived/` para la bandeja archivada.

### 5.2 Membresía y permisos finos

1. Bajo **`/api/v1/chats/{chat_id}/members/`** se listan miembros, se añaden o actualizan, se cambian roles (**`.../{member_id}/role/`**) o el propio usuario sale con **`leave/`**.
2. El servidor cruza membresía + permisos declarados (`LIST_MESSAGES`, etc.) antes de responder; no hay matriz usuario→permiso almacenada **en** este servicio.

### 5.3 Historial, lectura y conversación activa

1. **`GET .../chats/{chat_id}/messages/`** pagina el historial cuando basta REST.
2. Para envío/regeneración y eventos fluidos suele usarse **WebSocket** (`/ws/…` según entorno — [websockets.md](websockets.md)).
3. **Marcar leídos**: **POST** `.../messages/read/` con el cursor de lectura del producto.
4. Operaciones sobre **un** mensaje: borrado (**DELETE** `.../{message_id}/`), bookmark, pin del mensaje, feedback, hilo (**`thread/`**) y export puntual (**export/pdf/**), según constantes en [permissions.md](permissions.md).

### 5.4 Hilos alrededor de un mensaje ancla

Los mensajes pueden tener respuestas en hilo (endpoints **`thread`** en REST): lectura o añadir respuesta con `LIST_THREAD_REPLIES` y `ADD_THREAD_REPLY`.

### 5.5 Compartición y callbacks

1. **Share links** bajo **`/api/v1/chats/{chat_id}/share-links/`** generan tokens; el público puede leer mensajes vía **`/api/v1/share/{token}/messages/`** (sin reproducir necesariamente toda la matriz JWT del chat íntimo).
2. **Webhooks** bajo **`.../webhooks/`** despachan a URLs externas ante eventos suscritos (creación de mensajes, ciclo de miembros, lock…).

### 5.6 Exportaciones

Endpoints bajo **`.../messages/export/...`** cubren PDF, Markdown, JSON y extracts orientados a IA; un mensaje aislado puede exportarse en PDF (**`messages/{message_id}/export/pdf/`**). Requieren `EXPORT_CHAT` donde aplique ([permissions.md](permissions.md)).

### 5.7 Salud operativa

**`GET /api/v1/health`** resume **PostgreSQL** y **Redis**; ver [api-overview.md](api-overview.md).

---

## 6. Qué **no** centraliza este servicio

- **Emisión o revocación de JWT** ni el catálogo maestro permiso‑usuario persistente fuera del claim que ya trae cada petición validada contra el **servicio de autenticación** configurado.
- **Mandatory Access Control** sobre documentos institucionales (**colecciones, clearance, compartimentos**) — ese catálogo vive en el **document collection service** u homólogos.
- **Ejecución del modelo LLM**, transcripción pesada de medios externos o almacenamiento de binarios grandes: este servicio orquesta y persiste mensajes/metadata; otros componentes ejecutan trabajo pesado cuando el diseño Aura lo delega así.

---

## 7. Lecturas recomendadas en este mismo directorio

| Documento | Para qué sirve |
|-----------|----------------|
| [api-overview.md](api-overview.md) | Prefijos `/api/v1`, autenticación, paginación, OpenAPI/Swagger, health, rutas públicas de share. |
| [endpoints.md](endpoints.md) | Mapa de rutas REST, método, permiso y uso. |
| [permissions.md](permissions.md) | Constantes por dominio funcional ↔ operaciones. |
| [errors-and-status-codes.md](errors-and-status-codes.md) | Formato JSON de error y códigos HTTP. |
| [websockets.md](websockets.md) | Contrato tiempo real para envío/recibir mensajes en el chat. |

Con esto deberías poder explicar en una reunión **qué problema resuelve** el servicio, **qué tablas representan**, **cuándo prefieres WS frente a REST**, y **en qué orden** suelen tocarse las piezas sin abrir el código línea a línea.
