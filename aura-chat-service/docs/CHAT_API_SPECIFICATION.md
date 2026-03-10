# Aura Chat Service - API Specification

## Índice

1. [Modelos y Entidades](#1-modelos-y-entidades)
2. [Endpoints REST](#2-endpoints-rest)
3. [Flujo Chat Completion](#3-flujo-chat-completion)
4. [Ejemplos cURL](#4-ejemplos-curl)
5. [Consideraciones de Seguridad](#5-consideraciones-de-seguridad)
6. [Clasificación MVP vs Nice-to-Have](#6-clasificación-mvp-vs-nice-to-have)

---

## 1. Modelos y Entidades

### 1.1 Diagrama de Relaciones

```
┌─────────────────┐       ┌─────────────────┐
│  Conversation   │───1:N─│     Message     │
└─────────────────┘       └─────────────────┘
        │                         │
        │                         ├───1:N───┌─────────────────┐
        │                         │         │   Attachment    │
        │                         │         └─────────────────┘
        │                         │
        │                         └───1:N───┌─────────────────┐
        │                                   │    ToolCall     │
        │                                   └─────────────────┘
        │
        └───────────────────────────────────────────────────────
                              user_id (FK a auth_user)
```

### 1.2 Entidad: Conversation

Representa un thread/conversación completa.

```sql
CREATE TYPE conversation_status AS ENUM ('active', 'archived');

CREATE TABLE conversation (
    -- Identificadores
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Datos de la conversación
    title           VARCHAR(255),                           -- Título (puede ser null, auto-generado)
    system_prompt   TEXT,                                   -- System prompt personalizado
    model           VARCHAR(100) DEFAULT 'default',         -- Modelo LLM a usar
    status          conversation_status DEFAULT 'active',
    
    -- Metadata JSON para extensibilidad
    metadata        JSONB DEFAULT '{}',
    
    -- Contadores (desnormalizados para performance)
    message_count   INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    
    -- Auditoría y soft delete
    user_id         BIGINT NOT NULL,                        -- Dueño de la conversación
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE,
    deleted_at      TIMESTAMP WITH TIME ZONE,               -- Soft delete
    
    -- Foreign Keys
    CONSTRAINT fk_conversation_user FOREIGN KEY (user_id) 
        REFERENCES auth_user(id) ON DELETE CASCADE
);

-- Índices recomendados
CREATE INDEX idx_conversation_user_id ON conversation(user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_conversation_user_created ON conversation(user_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_conversation_status ON conversation(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_conversation_deleted_at ON conversation(deleted_at) WHERE deleted_at IS NOT NULL;
```

**Campos:**

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `id` | UUID | No | Identificador único (UUID v4) |
| `title` | VARCHAR(255) | Sí | Título de la conversación |
| `system_prompt` | TEXT | Sí | Prompt de sistema personalizado |
| `model` | VARCHAR(100) | No | Modelo LLM (default, gpt-4, llama3, etc.) |
| `status` | ENUM | No | Estado: active, archived |
| `metadata` | JSONB | No | Metadata extensible |
| `message_count` | INTEGER | No | Contador de mensajes |
| `total_tokens` | INTEGER | No | Total de tokens consumidos |
| `user_id` | BIGINT | No | FK al usuario dueño |
| `created_at` | TIMESTAMPTZ | No | Fecha de creación |
| `updated_at` | TIMESTAMPTZ | Sí | Última actualización |
| `deleted_at` | TIMESTAMPTZ | Sí | Soft delete timestamp |

---

### 1.3 Entidad: Message

Representa un mensaje individual dentro de una conversación.

```sql
CREATE TYPE message_role AS ENUM ('system', 'user', 'assistant', 'tool');
CREATE TYPE message_status AS ENUM ('draft', 'streaming', 'complete', 'error');

CREATE TABLE message (
    -- Identificadores
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL,
    
    -- Contenido del mensaje
    role                message_role NOT NULL,
    content             TEXT,                                   -- Puede ser null si hay tool_calls
    
    -- Estado y metadata
    status              message_status DEFAULT 'complete',
    
    -- Tokens (opcional, para tracking de uso)
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    total_tokens        INTEGER,
    
    -- Para respuestas del asistente
    model_used          VARCHAR(100),                           -- Modelo que generó la respuesta
    finish_reason       VARCHAR(50),                            -- stop, length, tool_calls, error
    
    -- Metadata extensible
    metadata            JSONB DEFAULT '{}',
    
    -- Para mensajes de tipo 'tool' (respuesta de una tool call)
    tool_call_id        VARCHAR(100),                           -- ID de la tool call que responde
    
    -- Orden dentro de la conversación
    sequence_number     INTEGER NOT NULL,
    
    -- Auditoría y soft delete
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE,
    deleted_at          TIMESTAMP WITH TIME ZONE,
    
    -- Foreign Keys
    CONSTRAINT fk_message_conversation FOREIGN KEY (conversation_id) 
        REFERENCES conversation(id) ON DELETE CASCADE
);

-- Índices recomendados
CREATE INDEX idx_message_conversation_id ON message(conversation_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_message_conversation_seq ON message(conversation_id, sequence_number) WHERE deleted_at IS NULL;
CREATE INDEX idx_message_role ON message(conversation_id, role) WHERE deleted_at IS NULL;
CREATE INDEX idx_message_status ON message(status) WHERE status IN ('draft', 'streaming');
CREATE INDEX idx_message_tool_call_id ON message(tool_call_id) WHERE tool_call_id IS NOT NULL;
```

**Campos:**

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `id` | UUID | No | Identificador único |
| `conversation_id` | UUID | No | FK a conversation |
| `role` | ENUM | No | system, user, assistant, tool |
| `content` | TEXT | Sí | Contenido del mensaje |
| `status` | ENUM | No | draft, streaming, complete, error |
| `prompt_tokens` | INTEGER | Sí | Tokens del prompt |
| `completion_tokens` | INTEGER | Sí | Tokens de la respuesta |
| `total_tokens` | INTEGER | Sí | Total de tokens |
| `model_used` | VARCHAR(100) | Sí | Modelo que generó la respuesta |
| `finish_reason` | VARCHAR(50) | Sí | Razón de finalización |
| `metadata` | JSONB | No | Metadata extensible |
| `tool_call_id` | VARCHAR(100) | Sí | ID de tool call (para role=tool) |
| `sequence_number` | INTEGER | No | Orden en la conversación |
| `created_at` | TIMESTAMPTZ | No | Fecha de creación |
| `updated_at` | TIMESTAMPTZ | Sí | Última actualización |
| `deleted_at` | TIMESTAMPTZ | Sí | Soft delete |

---

### 1.4 Entidad: Attachment

Representa archivos adjuntos a un mensaje.

```sql
CREATE TYPE attachment_type AS ENUM ('image', 'file', 'audio', 'video');

CREATE TABLE attachment (
    -- Identificadores
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id      UUID NOT NULL,
    
    -- Información del archivo
    file_name       VARCHAR(255) NOT NULL,
    file_type       attachment_type NOT NULL,
    mime_type       VARCHAR(100) NOT NULL,
    file_size       BIGINT NOT NULL,                        -- Tamaño en bytes
    storage_path    VARCHAR(500) NOT NULL,                  -- Path en MinIO/S3
    
    -- Metadata adicional (dimensiones de imagen, duración de audio, etc.)
    metadata        JSONB DEFAULT '{}',
    
    -- Para imágenes procesadas por vision models
    description     TEXT,                                   -- Descripción generada por AI
    
    -- Auditoría
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at      TIMESTAMP WITH TIME ZONE,
    
    -- Foreign Keys
    CONSTRAINT fk_attachment_message FOREIGN KEY (message_id) 
        REFERENCES message(id) ON DELETE CASCADE
);

-- Índices recomendados
CREATE INDEX idx_attachment_message_id ON attachment(message_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_attachment_type ON attachment(file_type) WHERE deleted_at IS NULL;
```

**Campos:**

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `id` | UUID | No | Identificador único |
| `message_id` | UUID | No | FK a message |
| `file_name` | VARCHAR(255) | No | Nombre original del archivo |
| `file_type` | ENUM | No | image, file, audio, video |
| `mime_type` | VARCHAR(100) | No | MIME type (image/png, etc.) |
| `file_size` | BIGINT | No | Tamaño en bytes |
| `storage_path` | VARCHAR(500) | No | Path en storage (MinIO) |
| `metadata` | JSONB | No | Metadata extensible |
| `description` | TEXT | Sí | Descripción AI del archivo |
| `created_at` | TIMESTAMPTZ | No | Fecha de creación |
| `deleted_at` | TIMESTAMPTZ | Sí | Soft delete |

---

### 1.5 Entidad: ToolCall

Representa llamadas a funciones/herramientas solicitadas por el asistente.

```sql
CREATE TYPE tool_call_status AS ENUM ('pending', 'executing', 'completed', 'failed');

CREATE TABLE tool_call (
    -- Identificadores
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id      UUID NOT NULL,                          -- Mensaje del assistant que solicita la tool
    tool_call_id    VARCHAR(100) NOT NULL UNIQUE,           -- ID generado por el LLM
    
    -- Información de la herramienta
    tool_type       VARCHAR(50) DEFAULT 'function',         -- function, code_interpreter, etc.
    function_name   VARCHAR(255) NOT NULL,
    function_args   JSONB NOT NULL,                         -- Argumentos de la función
    
    -- Resultado
    status          tool_call_status DEFAULT 'pending',
    result          TEXT,                                   -- Resultado de la ejecución
    error_message   TEXT,                                   -- Mensaje de error si falló
    
    -- Timing
    started_at      TIMESTAMP WITH TIME ZONE,
    completed_at    TIMESTAMP WITH TIME ZONE,
    
    -- Auditoría
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign Keys
    CONSTRAINT fk_tool_call_message FOREIGN KEY (message_id) 
        REFERENCES message(id) ON DELETE CASCADE
);

-- Índices recomendados
CREATE INDEX idx_tool_call_message_id ON tool_call(message_id);
CREATE INDEX idx_tool_call_tool_call_id ON tool_call(tool_call_id);
CREATE INDEX idx_tool_call_status ON tool_call(status) WHERE status IN ('pending', 'executing');
```

**Campos:**

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `id` | UUID | No | Identificador único interno |
| `message_id` | UUID | No | FK al mensaje del assistant |
| `tool_call_id` | VARCHAR(100) | No | ID único de la tool call (del LLM) |
| `tool_type` | VARCHAR(50) | No | Tipo: function, code_interpreter |
| `function_name` | VARCHAR(255) | No | Nombre de la función |
| `function_args` | JSONB | No | Argumentos JSON |
| `status` | ENUM | No | pending, executing, completed, failed |
| `result` | TEXT | Sí | Resultado de la ejecución |
| `error_message` | TEXT | Sí | Error si falló |
| `started_at` | TIMESTAMPTZ | Sí | Inicio de ejecución |
| `completed_at` | TIMESTAMPTZ | Sí | Fin de ejecución |
| `created_at` | TIMESTAMPTZ | No | Fecha de creación |

---

### 1.6 Modelos SQLAlchemy (Python)

```python
# app/domain/models/conversation.py
from sqlalchemy import Column, String, Text, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.domain.models.base import Base


class ConversationStatus(enum.Enum):
    active = "active"
    archived = "archived"


class Conversation(Base):
    __tablename__ = "conversation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=True)
    system_prompt = Column(Text, nullable=True)
    model = Column(String(100), default="default")
    status = Column(Enum(ConversationStatus), default=ConversationStatus.active)
    metadata = Column(JSONB, default=dict)
    message_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    user_id = Column(Integer, ForeignKey("auth_user.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    messages = relationship("Message", back_populates="conversation", 
                          order_by="Message.sequence_number")
```

```python
# app/domain/models/message.py
from sqlalchemy import Column, String, Text, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.domain.models.base import Base


class MessageRole(enum.Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class MessageStatus(enum.Enum):
    draft = "draft"
    streaming = "streaming"
    complete = "complete"
    error = "error"


class Message(Base):
    __tablename__ = "message"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversation.id"), nullable=False)
    
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=True)
    status = Column(Enum(MessageStatus), default=MessageStatus.complete)
    
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    
    model_used = Column(String(100), nullable=True)
    finish_reason = Column(String(50), nullable=True)
    metadata = Column(JSONB, default=dict)
    tool_call_id = Column(String(100), nullable=True)
    sequence_number = Column(Integer, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    attachments = relationship("Attachment", back_populates="message")
    tool_calls = relationship("ToolCall", back_populates="message")
```

```python
# app/domain/models/attachment.py
from sqlalchemy import Column, String, Text, BigInteger, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.domain.models.base import Base


class AttachmentType(enum.Enum):
    image = "image"
    file = "file"
    audio = "audio"
    video = "video"


class Attachment(Base):
    __tablename__ = "attachment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("message.id"), nullable=False)
    
    file_name = Column(String(255), nullable=False)
    file_type = Column(Enum(AttachmentType), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    storage_path = Column(String(500), nullable=False)
    metadata = Column(JSONB, default=dict)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    message = relationship("Message", back_populates="attachments")
```

```python
# app/domain/models/tool_call.py
from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.domain.models.base import Base


class ToolCallStatus(enum.Enum):
    pending = "pending"
    executing = "executing"
    completed = "completed"
    failed = "failed"


class ToolCall(Base):
    __tablename__ = "tool_call"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("message.id"), nullable=False)
    tool_call_id = Column(String(100), unique=True, nullable=False)
    
    tool_type = Column(String(50), default="function")
    function_name = Column(String(255), nullable=False)
    function_args = Column(JSONB, nullable=False)
    
    status = Column(Enum(ToolCallStatus), default=ToolCallStatus.pending)
    result = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    message = relationship("Message", back_populates="tool_calls")
```

---

## 2. Endpoints REST

### 2.1 Resumen de Endpoints

| Método | Ruta | Descripción | MVP |
|--------|------|-------------|-----|
| `POST` | `/api/v1/conversations` | Crear conversación | ✅ |
| `GET` | `/api/v1/conversations` | Listar conversaciones | ✅ |
| `GET` | `/api/v1/conversations/{id}` | Obtener conversación | ✅ |
| `PATCH` | `/api/v1/conversations/{id}` | Actualizar conversación | ✅ |
| `DELETE` | `/api/v1/conversations/{id}` | Eliminar conversación (soft) | ✅ |
| `POST` | `/api/v1/conversations/{id}/messages` | Enviar mensaje (no-stream) | ✅ |
| `POST` | `/api/v1/conversations/{id}/messages/stream` | Enviar mensaje (stream) | ✅ |
| `GET` | `/api/v1/conversations/{id}/messages` | Listar mensajes | ✅ |
| `GET` | `/api/v1/conversations/{id}/messages/{msg_id}` | Obtener mensaje | ⭐ |
| `DELETE` | `/api/v1/conversations/{id}/messages/{msg_id}` | Eliminar mensaje | ⭐ |
| `POST` | `/api/v1/conversations/{id}/messages/{msg_id}/regenerate` | Regenerar respuesta | ⭐ |
| `POST` | `/api/v1/chat/completions` | Chat completion (OpenAI-compatible) | ⭐ |
| `POST` | `/api/v1/messages/{msg_id}/attachments` | Subir adjunto | ⭐ |
| `GET` | `/api/v1/messages/{msg_id}/attachments` | Listar adjuntos | ⭐ |
| `POST` | `/api/v1/tool-calls/{tool_call_id}/result` | Enviar resultado de tool | ⭐ |

**Leyenda:** ✅ MVP | ⭐ Nice-to-have

---

### 2.2 Detalle de Endpoints

#### 2.2.1 POST /api/v1/conversations

Crea una nueva conversación.

**Auth:** Bearer JWT requerido

**Request Body:**
```json
{
  "title": "Mi conversación",           // opcional
  "system_prompt": "Eres un asistente útil...",  // opcional
  "model": "llama3",                    // opcional, default: "default"
  "metadata": {                         // opcional
    "tags": ["trabajo", "proyecto-x"]
  }
}
```

**Response 201 Created:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Mi conversación",
  "system_prompt": "Eres un asistente útil...",
  "model": "llama3",
  "status": "active",
  "metadata": {
    "tags": ["trabajo", "proyecto-x"]
  },
  "message_count": 0,
  "total_tokens": 0,
  "created_at": "2026-01-13T10:30:00Z",
  "updated_at": null
}
```

**Códigos de estado:**
- `201 Created` - Conversación creada exitosamente
- `400 Bad Request` - Datos inválidos
- `401 Unauthorized` - Token JWT inválido o ausente
- `422 Unprocessable Entity` - Error de validación

---

#### 2.2.2 GET /api/v1/conversations

Lista las conversaciones del usuario autenticado.

**Auth:** Bearer JWT requerido

**Query Parameters:**
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `cursor` | string | null | Cursor para paginación |
| `limit` | integer | 20 | Cantidad por página (max: 100) |
| `status` | string | null | Filtrar por status (active, archived) |
| `search` | string | null | Buscar en título |
| `sort` | string | "created_at" | Campo de ordenamiento |
| `order` | string | "desc" | Dirección (asc, desc) |

**Response 200 OK:**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Mi conversación",
      "model": "llama3",
      "status": "active",
      "message_count": 15,
      "total_tokens": 2340,
      "created_at": "2026-01-13T10:30:00Z",
      "updated_at": "2026-01-13T11:45:00Z",
      "last_message_preview": "Claro, te explico cómo..."
    }
  ],
  "pagination": {
    "next_cursor": "eyJpZCI6IjU1MGU4NDAwLWUyOWItNDFkNC1hNzE2LTQ0NjY1NTQ0MDAwMCIsImNyZWF0ZWRfYXQiOiIyMDI2LTAxLTEzVDEwOjMwOjAwWiJ9",
    "has_more": true,
    "total_count": 42
  }
}
```

---

#### 2.2.3 GET /api/v1/conversations/{id}

Obtiene una conversación específica.

**Auth:** Bearer JWT requerido

**Path Parameters:**
- `id` (UUID) - ID de la conversación

**Response 200 OK:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Mi conversación",
  "system_prompt": "Eres un asistente útil...",
  "model": "llama3",
  "status": "active",
  "metadata": {
    "tags": ["trabajo", "proyecto-x"]
  },
  "message_count": 15,
  "total_tokens": 2340,
  "created_at": "2026-01-13T10:30:00Z",
  "updated_at": "2026-01-13T11:45:00Z"
}
```

**Códigos de estado:**
- `200 OK` - Éxito
- `401 Unauthorized` - No autenticado
- `403 Forbidden` - No es dueño de la conversación
- `404 Not Found` - Conversación no existe

---

#### 2.2.4 PATCH /api/v1/conversations/{id}

Actualiza una conversación (título, system_prompt, status, metadata).

**Auth:** Bearer JWT requerido

**Request Body:**
```json
{
  "title": "Nuevo título",              // opcional
  "system_prompt": "Nuevo prompt...",   // opcional
  "status": "archived",                 // opcional
  "metadata": {                         // opcional (merge con existente)
    "tags": ["actualizado"]
  }
}
```

**Response 200 OK:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Nuevo título",
  "system_prompt": "Nuevo prompt...",
  "model": "llama3",
  "status": "archived",
  "metadata": {
    "tags": ["actualizado"]
  },
  "message_count": 15,
  "total_tokens": 2340,
  "created_at": "2026-01-13T10:30:00Z",
  "updated_at": "2026-01-13T12:00:00Z"
}
```

---

#### 2.2.5 DELETE /api/v1/conversations/{id}

Elimina una conversación (soft delete).

**Auth:** Bearer JWT requerido

**Response 204 No Content**

**Códigos de estado:**
- `204 No Content` - Eliminado exitosamente
- `401 Unauthorized` - No autenticado
- `403 Forbidden` - No es dueño
- `404 Not Found` - No existe

---

#### 2.2.6 POST /api/v1/conversations/{id}/messages

Envía un mensaje y obtiene respuesta del asistente (modo no-streaming).

**Auth:** Bearer JWT requerido

**Request Body:**
```json
{
  "content": "¿Cómo funciona la fotosíntesis?",
  "role": "user",                       // opcional, default: "user"
  "attachments": [                      // opcional
    {
      "file_id": "attachment-uuid",
      "type": "image"
    }
  ],
  "tools": [                            // opcional - definición de tools disponibles
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Obtiene el clima actual",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {
              "type": "string",
              "description": "Ciudad"
            }
          },
          "required": ["location"]
        }
      }
    }
  ],
  "metadata": {}                        // opcional
}
```

**Response 200 OK:**
```json
{
  "user_message": {
    "id": "msg-user-uuid",
    "role": "user",
    "content": "¿Cómo funciona la fotosíntesis?",
    "status": "complete",
    "sequence_number": 1,
    "created_at": "2026-01-13T10:30:00Z"
  },
  "assistant_message": {
    "id": "msg-assistant-uuid",
    "role": "assistant",
    "content": "La fotosíntesis es el proceso mediante el cual las plantas...",
    "status": "complete",
    "model_used": "llama3",
    "finish_reason": "stop",
    "prompt_tokens": 45,
    "completion_tokens": 230,
    "total_tokens": 275,
    "sequence_number": 2,
    "tool_calls": [],
    "created_at": "2026-01-13T10:30:05Z"
  },
  "conversation": {
    "id": "conv-uuid",
    "message_count": 2,
    "total_tokens": 275
  }
}
```

**Response con Tool Calls:**
```json
{
  "user_message": { ... },
  "assistant_message": {
    "id": "msg-assistant-uuid",
    "role": "assistant",
    "content": null,
    "status": "complete",
    "finish_reason": "tool_calls",
    "tool_calls": [
      {
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "get_weather",
          "arguments": "{\"location\": \"Buenos Aires\"}"
        }
      }
    ],
    "created_at": "2026-01-13T10:30:05Z"
  }
}
```

---

#### 2.2.7 POST /api/v1/conversations/{id}/messages/stream

Envía un mensaje y obtiene respuesta en streaming (SSE).

**Auth:** Bearer JWT requerido

**Request Body:** (igual que no-streaming)
```json
{
  "content": "Explicame la teoría de la relatividad",
  "role": "user"
}
```

**Response: text/event-stream**

```
event: message_start
data: {"message_id": "msg-uuid", "conversation_id": "conv-uuid"}

event: content_delta
data: {"delta": "La teoría de la "}

event: content_delta
data: {"delta": "relatividad, propuesta por "}

event: content_delta
data: {"delta": "Albert Einstein..."}

event: tool_call_start
data: {"tool_call": {"id": "call_123", "type": "function", "function": {"name": "search", "arguments": ""}}}

event: tool_call_delta
data: {"tool_call_id": "call_123", "arguments_delta": "{\"query\":"}

event: tool_call_delta
data: {"tool_call_id": "call_123", "arguments_delta": " \"relatividad\"}"}

event: message_complete
data: {"message_id": "msg-uuid", "finish_reason": "stop", "usage": {"prompt_tokens": 50, "completion_tokens": 180, "total_tokens": 230}}

event: done
data: [DONE]
```

**Eventos SSE:**

| Evento | Descripción |
|--------|-------------|
| `message_start` | Inicio del mensaje, incluye IDs |
| `content_delta` | Fragmento de texto |
| `tool_call_start` | Inicio de una tool call |
| `tool_call_delta` | Fragmento de argumentos de tool |
| `message_complete` | Mensaje completo, incluye usage |
| `error` | Error durante streaming |
| `done` | Fin del stream |

---

#### 2.2.8 GET /api/v1/conversations/{id}/messages

Lista los mensajes de una conversación.

**Auth:** Bearer JWT requerido

**Query Parameters:**
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `cursor` | string | null | Cursor para paginación |
| `limit` | integer | 50 | Cantidad por página (max: 200) |
| `order` | string | "asc" | Orden (asc=cronológico, desc=reverso) |
| `include_deleted` | boolean | false | Incluir mensajes eliminados |

**Response 200 OK:**
```json
{
  "data": [
    {
      "id": "msg-uuid-1",
      "role": "system",
      "content": "Eres un asistente útil...",
      "status": "complete",
      "sequence_number": 0,
      "created_at": "2026-01-13T10:30:00Z"
    },
    {
      "id": "msg-uuid-2",
      "role": "user",
      "content": "Hola, ¿cómo estás?",
      "status": "complete",
      "sequence_number": 1,
      "attachments": [],
      "created_at": "2026-01-13T10:30:01Z"
    },
    {
      "id": "msg-uuid-3",
      "role": "assistant",
      "content": "¡Hola! Estoy muy bien, gracias...",
      "status": "complete",
      "model_used": "llama3",
      "finish_reason": "stop",
      "prompt_tokens": 25,
      "completion_tokens": 45,
      "total_tokens": 70,
      "sequence_number": 2,
      "tool_calls": [],
      "created_at": "2026-01-13T10:30:03Z"
    }
  ],
  "pagination": {
    "next_cursor": null,
    "has_more": false,
    "total_count": 3
  }
}
```

---

#### 2.2.9 POST /api/v1/tool-calls/{tool_call_id}/result

Envía el resultado de una tool call para continuar la conversación.

**Auth:** Bearer JWT requerido

**Request Body:**
```json
{
  "result": "{\"temperature\": 22, \"condition\": \"sunny\"}",
  "is_error": false                     // opcional, default: false
}
```

**Response 200 OK:**
```json
{
  "tool_message": {
    "id": "msg-tool-uuid",
    "role": "tool",
    "content": "{\"temperature\": 22, \"condition\": \"sunny\"}",
    "tool_call_id": "call_abc123",
    "status": "complete",
    "created_at": "2026-01-13T10:30:10Z"
  },
  "assistant_message": {
    "id": "msg-assistant-uuid-2",
    "role": "assistant",
    "content": "El clima en Buenos Aires es soleado con 22°C...",
    "status": "complete",
    "finish_reason": "stop",
    "created_at": "2026-01-13T10:30:12Z"
  }
}
```

---

#### 2.2.10 POST /api/v1/chat/completions (OpenAI-compatible)

Endpoint compatible con la API de OpenAI para facilitar integración.

**Auth:** Bearer JWT requerido

**Request Body:**
```json
{
  "model": "llama3",
  "messages": [
    {"role": "system", "content": "Eres un asistente útil."},
    {"role": "user", "content": "¿Qué es Python?"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 1000,
  "tools": [],
  "conversation_id": "conv-uuid"        // extensión: asociar a conversación existente
}
```

**Response 200 OK (no-stream):**
```json
{
  "id": "chatcmpl-uuid",
  "object": "chat.completion",
  "created": 1736765400,
  "model": "llama3",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Python es un lenguaje de programación..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 30,
    "completion_tokens": 150,
    "total_tokens": 180
  },
  "conversation_id": "conv-uuid"
}
```

---

## 3. Flujo Chat Completion

### 3.1 Diagrama de Secuencia - Modo No-Streaming

```
┌──────┐          ┌─────────────┐          ┌──────────┐          ┌─────┐
│Client│          │Chat Service │          │LLM Service│          │ DB  │
└──┬───┘          └──────┬──────┘          └────┬─────┘          └──┬──┘
   │                     │                      │                   │
   │ POST /messages      │                      │                   │
   │────────────────────>│                      │                   │
   │                     │                      │                   │
   │                     │ Validar JWT          │                   │
   │                     │──────────────────────────────────────────>
   │                     │                      │                   │
   │                     │ Verificar ownership  │                   │
   │                     │──────────────────────────────────────────>
   │                     │                      │                   │
   │                     │ Crear mensaje user   │                   │
   │                     │──────────────────────────────────────────>
   │                     │                      │                   │
   │                     │ Obtener historial    │                   │
   │                     │──────────────────────────────────────────>
   │                     │                      │                   │
   │                     │ POST /generate       │                   │
   │                     │─────────────────────>│                   │
   │                     │                      │                   │
   │                     │    Respuesta LLM     │                   │
   │                     │<─────────────────────│                   │
   │                     │                      │                   │
   │                     │ Crear mensaje assistant                  │
   │                     │──────────────────────────────────────────>
   │                     │                      │                   │
   │                     │ Actualizar conversation                  │
   │                     │──────────────────────────────────────────>
   │                     │                      │                   │
   │   200 OK + Response │                      │                   │
   │<────────────────────│                      │                   │
   │                     │                      │                   │
```

### 3.2 Diagrama de Secuencia - Modo Streaming (SSE)

```
┌──────┐          ┌─────────────┐          ┌──────────┐          ┌─────┐
│Client│          │Chat Service │          │LLM Service│          │ DB  │
└──┬───┘          └──────┬──────┘          └────┬─────┘          └──┬──┘
   │                     │                      │                   │
   │ POST /messages/stream                      │                   │
   │────────────────────>│                      │                   │
   │                     │                      │                   │
   │                     │ Validar + Crear msg user                 │
   │                     │──────────────────────────────────────────>
   │                     │                      │                   │
   │                     │ Crear msg assistant (status=streaming)   │
   │                     │──────────────────────────────────────────>
   │                     │                      │                   │
   │ SSE: message_start  │                      │                   │
   │<────────────────────│                      │                   │
   │                     │                      │                   │
   │                     │ POST /generate/stream│                   │
   │                     │─────────────────────>│                   │
   │                     │                      │                   │
   │                     │   chunk 1            │                   │
   │                     │<─────────────────────│                   │
   │ SSE: content_delta  │                      │                   │
   │<────────────────────│                      │                   │
   │                     │                      │                   │
   │                     │   chunk 2            │                   │
   │                     │<─────────────────────│                   │
   │ SSE: content_delta  │                      │                   │
   │<────────────────────│                      │                   │
   │                     │                      │                   │
   │                     │   [DONE]             │                   │
   │                     │<─────────────────────│                   │
   │                     │                      │                   │
   │                     │ Actualizar msg (status=complete)         │
   │                     │──────────────────────────────────────────>
   │                     │                      │                   │
   │ SSE: message_complete                      │                   │
   │<────────────────────│                      │                   │
   │                     │                      │                   │
   │ SSE: done           │                      │                   │
   │<────────────────────│                      │                   │
```

### 3.3 Pseudocódigo del Flujo

```python
async def send_message(
    conversation_id: UUID,
    request: SendMessageRequest,
    current_user: User,
    stream: bool = False
):
    # 1. Validar que la conversación existe y pertenece al usuario
    conversation = await conversation_repo.get_by_id(conversation_id)
    if not conversation:
        raise NotFoundError("Conversation not found")
    if conversation.user_id != current_user.id:
        raise ForbiddenError("Access denied")
    if conversation.deleted_at:
        raise NotFoundError("Conversation deleted")
    
    # 2. Obtener el siguiente sequence_number
    next_seq = await message_repo.get_next_sequence(conversation_id)
    
    # 3. Crear mensaje del usuario
    user_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.user,
        content=request.content,
        status=MessageStatus.complete,
        sequence_number=next_seq,
        metadata=request.metadata or {}
    )
    await message_repo.create(user_message)
    
    # 4. Procesar adjuntos si existen
    if request.attachments:
        for att in request.attachments:
            await attachment_service.link_to_message(att.file_id, user_message.id)
    
    # 5. Obtener historial de mensajes para contexto
    history = await message_repo.get_by_conversation(
        conversation_id,
        include_deleted=False
    )
    
    # 6. Preparar mensajes para el LLM
    llm_messages = []
    if conversation.system_prompt:
        llm_messages.append({
            "role": "system",
            "content": conversation.system_prompt
        })
    for msg in history:
        llm_messages.append({
            "role": msg.role.value,
            "content": msg.content
        })
    
    # 7. Crear mensaje del asistente (placeholder para streaming)
    assistant_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.assistant,
        content="" if stream else None,
        status=MessageStatus.streaming if stream else MessageStatus.draft,
        sequence_number=next_seq + 1,
        model_used=conversation.model
    )
    await message_repo.create(assistant_message)
    
    if stream:
        # 8a. Modo streaming
        return stream_response(
            assistant_message,
            llm_messages,
            request.tools,
            conversation
        )
    else:
        # 8b. Modo no-streaming
        response = await llm_service.generate(
            model=conversation.model,
            messages=llm_messages,
            tools=request.tools
        )
        
        # 9. Actualizar mensaje del asistente
        assistant_message.content = response.content
        assistant_message.status = MessageStatus.complete
        assistant_message.finish_reason = response.finish_reason
        assistant_message.prompt_tokens = response.usage.prompt_tokens
        assistant_message.completion_tokens = response.usage.completion_tokens
        assistant_message.total_tokens = response.usage.total_tokens
        await message_repo.update(assistant_message)
        
        # 10. Procesar tool calls si existen
        if response.tool_calls:
            for tc in response.tool_calls:
                tool_call = ToolCall(
                    message_id=assistant_message.id,
                    tool_call_id=tc.id,
                    tool_type=tc.type,
                    function_name=tc.function.name,
                    function_args=json.loads(tc.function.arguments)
                )
                await tool_call_repo.create(tool_call)
        
        # 11. Actualizar contadores de conversación
        conversation.message_count += 2
        conversation.total_tokens += response.usage.total_tokens
        conversation.updated_at = datetime.utcnow()
        await conversation_repo.update(conversation)
        
        return SendMessageResponse(
            user_message=user_message,
            assistant_message=assistant_message,
            conversation=conversation
        )


async def stream_response(
    assistant_message: Message,
    llm_messages: list,
    tools: list,
    conversation: Conversation
):
    """Generator para SSE streaming"""
    
    # Evento inicial
    yield create_sse_event("message_start", {
        "message_id": str(assistant_message.id),
        "conversation_id": str(conversation.id)
    })
    
    full_content = ""
    tool_calls = []
    usage = None
    finish_reason = None
    
    try:
        async for chunk in llm_service.generate_stream(
            model=conversation.model,
            messages=llm_messages,
            tools=tools
        ):
            if chunk.content_delta:
                full_content += chunk.content_delta
                yield create_sse_event("content_delta", {
                    "delta": chunk.content_delta
                })
            
            if chunk.tool_call_delta:
                # Manejar streaming de tool calls
                yield create_sse_event("tool_call_delta", {
                    "tool_call_id": chunk.tool_call_delta.id,
                    "arguments_delta": chunk.tool_call_delta.arguments
                })
            
            if chunk.finish_reason:
                finish_reason = chunk.finish_reason
            
            if chunk.usage:
                usage = chunk.usage
        
        # Actualizar mensaje en DB
        assistant_message.content = full_content
        assistant_message.status = MessageStatus.complete
        assistant_message.finish_reason = finish_reason
        if usage:
            assistant_message.prompt_tokens = usage.prompt_tokens
            assistant_message.completion_tokens = usage.completion_tokens
            assistant_message.total_tokens = usage.total_tokens
        await message_repo.update(assistant_message)
        
        # Actualizar conversación
        conversation.message_count += 2
        if usage:
            conversation.total_tokens += usage.total_tokens
        await conversation_repo.update(conversation)
        
        # Evento final
        yield create_sse_event("message_complete", {
            "message_id": str(assistant_message.id),
            "finish_reason": finish_reason,
            "usage": usage.dict() if usage else None
        })
        
    except Exception as e:
        assistant_message.status = MessageStatus.error
        assistant_message.metadata["error"] = str(e)
        await message_repo.update(assistant_message)
        
        yield create_sse_event("error", {
            "message": "Error generating response",
            "code": "generation_error"
        })
    
    finally:
        yield create_sse_event("done", "[DONE]")
```

### 3.4 Flujo con Tool Calls

```
1. Usuario envía mensaje
2. LLM responde con tool_calls (finish_reason="tool_calls")
3. Cliente recibe tool_calls en la respuesta
4. Cliente ejecuta las funciones localmente
5. Cliente envía resultados via POST /tool-calls/{id}/result
6. Servicio crea mensaje role="tool" con el resultado
7. Servicio llama al LLM con el historial actualizado
8. LLM genera respuesta final
9. Cliente recibe respuesta del asistente
```

---

## 4. Ejemplos cURL

### 4.1 Crear Conversación

```bash
curl -X POST 'http://localhost:8002/api/v1/conversations' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Consulta sobre Python",
    "system_prompt": "Eres un experto en Python. Responde de forma clara y con ejemplos de código.",
    "model": "llama3"
  }'
```

**Respuesta:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Consulta sobre Python",
  "system_prompt": "Eres un experto en Python...",
  "model": "llama3",
  "status": "active",
  "message_count": 0,
  "created_at": "2026-01-13T10:30:00Z"
}
```

### 4.2 Enviar Mensaje (No-Streaming)

```bash
curl -X POST 'http://localhost:8002/api/v1/conversations/550e8400-e29b-41d4-a716-446655440000/messages' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json' \
  -d '{
    "content": "¿Cómo puedo leer un archivo JSON en Python?"
  }'
```

**Respuesta:**
```json
{
  "user_message": {
    "id": "msg-user-123",
    "role": "user",
    "content": "¿Cómo puedo leer un archivo JSON en Python?",
    "status": "complete",
    "sequence_number": 1,
    "created_at": "2026-01-13T10:31:00Z"
  },
  "assistant_message": {
    "id": "msg-assistant-456",
    "role": "assistant",
    "content": "Para leer un archivo JSON en Python, puedes usar el módulo `json` de la biblioteca estándar:\n\n```python\nimport json\n\nwith open('archivo.json', 'r') as f:\n    data = json.load(f)\n\nprint(data)\n```\n\nEste código abre el archivo, lo parsea y lo convierte en un diccionario de Python.",
    "status": "complete",
    "model_used": "llama3",
    "finish_reason": "stop",
    "prompt_tokens": 85,
    "completion_tokens": 120,
    "total_tokens": 205,
    "sequence_number": 2,
    "created_at": "2026-01-13T10:31:05Z"
  }
}
```

### 4.3 Enviar Mensaje (Streaming)

```bash
curl -X POST 'http://localhost:8002/api/v1/conversations/550e8400-e29b-41d4-a716-446655440000/messages/stream' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -N \
  -d '{
    "content": "Explicame qué es un decorador en Python"
  }'
```

**Respuesta (SSE):**
```
event: message_start
data: {"message_id": "msg-789", "conversation_id": "550e8400-e29b-41d4-a716-446655440000"}

event: content_delta
data: {"delta": "Un decorador en Python es "}

event: content_delta
data: {"delta": "una función que modifica "}

event: content_delta
data: {"delta": "el comportamiento de otra función..."}

event: message_complete
data: {"message_id": "msg-789", "finish_reason": "stop", "usage": {"prompt_tokens": 90, "completion_tokens": 250, "total_tokens": 340}}

event: done
data: [DONE]
```

### 4.4 Listar Conversaciones

```bash
curl -X GET 'http://localhost:8002/api/v1/conversations?limit=10&status=active' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

**Respuesta:**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Consulta sobre Python",
      "model": "llama3",
      "status": "active",
      "message_count": 4,
      "total_tokens": 890,
      "created_at": "2026-01-13T10:30:00Z",
      "updated_at": "2026-01-13T10:35:00Z",
      "last_message_preview": "Un decorador en Python es..."
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "title": "Ayuda con Docker",
      "model": "llama3",
      "status": "active",
      "message_count": 8,
      "total_tokens": 1520,
      "created_at": "2026-01-12T15:00:00Z",
      "updated_at": "2026-01-12T15:30:00Z",
      "last_message_preview": "Para crear un Dockerfile..."
    }
  ],
  "pagination": {
    "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0wMS0xMlQxNTowMDowMFoifQ==",
    "has_more": true,
    "total_count": 15
  }
}
```

### 4.5 Obtener Mensajes de una Conversación

```bash
curl -X GET 'http://localhost:8002/api/v1/conversations/550e8400-e29b-41d4-a716-446655440000/messages?limit=50' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

**Respuesta:**
```json
{
  "data": [
    {
      "id": "msg-system-001",
      "role": "system",
      "content": "Eres un experto en Python...",
      "status": "complete",
      "sequence_number": 0,
      "created_at": "2026-01-13T10:30:00Z"
    },
    {
      "id": "msg-user-123",
      "role": "user",
      "content": "¿Cómo puedo leer un archivo JSON en Python?",
      "status": "complete",
      "sequence_number": 1,
      "attachments": [],
      "created_at": "2026-01-13T10:31:00Z"
    },
    {
      "id": "msg-assistant-456",
      "role": "assistant",
      "content": "Para leer un archivo JSON en Python...",
      "status": "complete",
      "model_used": "llama3",
      "finish_reason": "stop",
      "prompt_tokens": 85,
      "completion_tokens": 120,
      "total_tokens": 205,
      "sequence_number": 2,
      "tool_calls": [],
      "created_at": "2026-01-13T10:31:05Z"
    }
  ],
  "pagination": {
    "next_cursor": null,
    "has_more": false,
    "total_count": 3
  }
}
```

### 4.6 Renombrar Conversación

```bash
curl -X PATCH 'http://localhost:8002/api/v1/conversations/550e8400-e29b-41d4-a716-446655440000' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Tutorial Python - JSON y archivos"
  }'
```

### 4.7 Eliminar Conversación (Soft Delete)

```bash
curl -X DELETE 'http://localhost:8002/api/v1/conversations/550e8400-e29b-41d4-a716-446655440000' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

**Respuesta:** `204 No Content`

### 4.8 Enviar Resultado de Tool Call

```bash
curl -X POST 'http://localhost:8002/api/v1/tool-calls/call_abc123/result' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json' \
  -d '{
    "result": "{\"temperature\": 22, \"condition\": \"sunny\", \"humidity\": 65}"
  }'
```

---

## 5. Consideraciones de Seguridad

### 5.1 Autenticación y Autorización

```python
# Middleware de autenticación JWT
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        user = await user_repo.get_by_id(int(user_id))
        if not user or user.deleted_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
```

### 5.2 Autorización por Recurso

```python
# Verificar ownership de conversación
async def verify_conversation_ownership(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user)
) -> Conversation:
    conversation = await conversation_repo.get_by_id(conversation_id)
    
    if not conversation or conversation.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return conversation
```

### 5.3 Rate Limiting

```python
# Configuración de rate limiting con Redis
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

# Límites recomendados
RATE_LIMITS = {
    "conversations_create": "10/minute",      # Crear conversaciones
    "messages_send": "30/minute",             # Enviar mensajes
    "messages_stream": "20/minute",           # Streaming
    "conversations_list": "60/minute",        # Listar
    "global": "1000/hour"                     # Global por usuario
}

# Aplicar en endpoints
@router.post("/conversations", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def create_conversation(...):
    ...

@router.post("/conversations/{id}/messages", dependencies=[Depends(RateLimiter(times=30, seconds=60))])
async def send_message(...):
    ...
```

### 5.4 Validaciones de Input

```python
from pydantic import BaseModel, Field, validator
import re

class CreateConversationRequest(BaseModel):
    title: str | None = Field(None, max_length=255)
    system_prompt: str | None = Field(None, max_length=10000)
    model: str = Field("default", max_length=100)
    metadata: dict = Field(default_factory=dict)
    
    @validator('title')
    def sanitize_title(cls, v):
        if v:
            # Remover caracteres potencialmente peligrosos
            v = re.sub(r'[<>"\']', '', v)
        return v
    
    @validator('metadata')
    def validate_metadata_size(cls, v):
        import json
        if len(json.dumps(v)) > 10000:
            raise ValueError("Metadata too large")
        return v


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=100000)
    role: str = Field("user", pattern="^(user|system)$")
    attachments: list[AttachmentRef] | None = Field(None, max_items=10)
    tools: list[ToolDefinition] | None = Field(None, max_items=50)
    metadata: dict = Field(default_factory=dict)
    
    @validator('content')
    def validate_content(cls, v):
        # Prevenir inyección de prompts maliciosos (básico)
        # En producción, usar técnicas más avanzadas
        if v.count('\n') > 1000:
            raise ValueError("Too many line breaks")
        return v
```

### 5.5 Idempotency

```python
# Header de idempotency para operaciones de escritura
IDEMPOTENCY_HEADER = "X-Idempotency-Key"

async def check_idempotency(
    idempotency_key: str | None = Header(None, alias=IDEMPOTENCY_HEADER),
    current_user: User = Depends(get_current_user)
) -> str | None:
    if not idempotency_key:
        return None
    
    # Verificar si ya existe una respuesta para esta key
    cache_key = f"idempotency:{current_user.id}:{idempotency_key}"
    cached_response = await redis.get(cache_key)
    
    if cached_response:
        return json.loads(cached_response)
    
    return idempotency_key


async def store_idempotency_response(
    key: str,
    user_id: int,
    response: dict,
    ttl: int = 86400  # 24 horas
):
    cache_key = f"idempotency:{user_id}:{key}"
    await redis.setex(cache_key, ttl, json.dumps(response))
```

### 5.6 Paginación Segura

```python
from base64 import b64encode, b64decode
import json

def encode_cursor(data: dict) -> str:
    """Codifica cursor de paginación"""
    return b64encode(json.dumps(data).encode()).decode()

def decode_cursor(cursor: str) -> dict:
    """Decodifica cursor de paginación"""
    try:
        return json.loads(b64decode(cursor.encode()).decode())
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cursor"
        )

# Uso en query
async def list_conversations(
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    query = select(Conversation).where(
        Conversation.user_id == current_user.id,
        Conversation.deleted_at.is_(None)
    )
    
    if cursor:
        cursor_data = decode_cursor(cursor)
        query = query.where(
            Conversation.created_at < cursor_data["created_at"]
        )
    
    query = query.order_by(Conversation.created_at.desc()).limit(limit + 1)
    
    results = await db.execute(query)
    conversations = results.scalars().all()
    
    has_more = len(conversations) > limit
    if has_more:
        conversations = conversations[:limit]
    
    next_cursor = None
    if has_more and conversations:
        next_cursor = encode_cursor({
            "created_at": conversations[-1].created_at.isoformat()
        })
    
    return {
        "data": conversations,
        "pagination": {
            "next_cursor": next_cursor,
            "has_more": has_more
        }
    }
```

### 5.7 Soft Delete

```python
# Todas las queries deben filtrar por deleted_at
async def get_conversation(id: UUID) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == id,
            Conversation.deleted_at.is_(None)  # Siempre filtrar
        )
    )
    return result.scalar_one_or_none()

# Soft delete
async def delete_conversation(id: UUID, user_id: int):
    await db.execute(
        update(Conversation)
        .where(
            Conversation.id == id,
            Conversation.user_id == user_id
        )
        .values(deleted_at=func.now())
    )
    
    # También soft-delete mensajes relacionados
    await db.execute(
        update(Message)
        .where(Message.conversation_id == id)
        .values(deleted_at=func.now())
    )
```

### 5.8 Headers de Seguridad

```python
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

---

## 6. Clasificación MVP vs Nice-to-Have

### 6.1 MVP (Minimum Viable Product)

| Endpoint | Prioridad | Justificación |
|----------|-----------|---------------|
| `POST /conversations` | P0 | Crear conversaciones |
| `GET /conversations` | P0 | Listar conversaciones del usuario |
| `GET /conversations/{id}` | P0 | Ver detalle de conversación |
| `PATCH /conversations/{id}` | P0 | Renombrar/actualizar |
| `DELETE /conversations/{id}` | P0 | Eliminar conversación |
| `POST /conversations/{id}/messages` | P0 | Enviar mensaje (core) |
| `POST /conversations/{id}/messages/stream` | P0 | Streaming (UX crítico) |
| `GET /conversations/{id}/messages` | P0 | Ver historial |

**Funcionalidades MVP:**
- ✅ CRUD de conversaciones
- ✅ Envío de mensajes con respuesta del LLM
- ✅ Streaming SSE
- ✅ Autenticación JWT
- ✅ Autorización por usuario
- ✅ Paginación cursor-based
- ✅ Soft delete
- ✅ Persistencia de historial

### 6.2 Nice-to-Have (Fase 2)

| Endpoint | Prioridad | Justificación |
|----------|-----------|---------------|
| `GET /conversations/{id}/messages/{msg_id}` | P1 | Detalle de mensaje individual |
| `DELETE /conversations/{id}/messages/{msg_id}` | P1 | Eliminar mensaje específico |
| `POST /conversations/{id}/messages/{msg_id}/regenerate` | P1 | Regenerar respuesta |
| `POST /chat/completions` | P1 | Compatibilidad OpenAI |
| `POST /messages/{msg_id}/attachments` | P2 | Subir adjuntos |
| `GET /messages/{msg_id}/attachments` | P2 | Listar adjuntos |
| `POST /tool-calls/{id}/result` | P2 | Function calling |

**Funcionalidades Nice-to-Have:**
- ⭐ Adjuntos (imágenes, archivos)
- ⭐ Tool/Function calling
- ⭐ Regenerar respuestas
- ⭐ API compatible con OpenAI
- ⭐ Búsqueda en conversaciones
- ⭐ Exportar conversaciones
- ⭐ Compartir conversaciones (read-only)
- ⭐ Templates de system prompts
- ⭐ Analytics de uso

---

## Apéndice A: Códigos de Error

```json
{
  "errors": {
    "CONVERSATION_NOT_FOUND": {
      "code": "CONVERSATION_NOT_FOUND",
      "status": 404,
      "message": "Conversation not found"
    },
    "MESSAGE_NOT_FOUND": {
      "code": "MESSAGE_NOT_FOUND", 
      "status": 404,
      "message": "Message not found"
    },
    "ACCESS_DENIED": {
      "code": "ACCESS_DENIED",
      "status": 403,
      "message": "You don't have access to this resource"
    },
    "INVALID_TOKEN": {
      "code": "INVALID_TOKEN",
      "status": 401,
      "message": "Invalid or expired token"
    },
    "RATE_LIMIT_EXCEEDED": {
      "code": "RATE_LIMIT_EXCEEDED",
      "status": 429,
      "message": "Too many requests, please try again later"
    },
    "VALIDATION_ERROR": {
      "code": "VALIDATION_ERROR",
      "status": 422,
      "message": "Request validation failed"
    },
    "LLM_ERROR": {
      "code": "LLM_ERROR",
      "status": 502,
      "message": "Error communicating with LLM service"
    },
    "STREAMING_ERROR": {
      "code": "STREAMING_ERROR",
      "status": 500,
      "message": "Error during response streaming"
    }
  }
}
```

---

## Apéndice B: Variables de Entorno

```bash
# Database
DATABASE_URL=postgresql://aura_root:aura_password@db:5432/aura_db

# JWT
JWT_SECRET=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# LLM Service
LLM_SERVICE_URL=http://aura-llm-service:8000
LLM_DEFAULT_MODEL=llama3

# Redis (para rate limiting e idempotency)
REDIS_URL=redis://memory_db:6379/0

# Storage (MinIO)
MINIO_ENDPOINT=storage:9000
MINIO_ACCESS_KEY=aura_root
MINIO_SECRET_KEY=aura_password
MINIO_BUCKET=chat-attachments

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_MESSAGES_PER_MINUTE=30
RATE_LIMIT_CONVERSATIONS_PER_MINUTE=10
```


