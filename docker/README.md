# Docker

Para levantar todo el entorno usá:

```
docker compose up -d
```

Ese es el modo normal sin GPU.
Si querés usar aceleración por GPU, entonces usá:

```
docker compose -f docker-compose.gpu.yml up -d
```

## Descripción de servicios

### aura-document-processing-service

- Nombre del contenedor: `aura-document-processing-service`
- Puerto expuesto: `8001`

### aura-llm-service

- Nombre del contenedor: `aura-llm-service`
- Puerto expuesto: `8000`

### db (PostgreSQL principal)

- Nombre: `db`
- Puerto: `5432`
- Usuario: `aura_root`
- Contraseña: `aura_password`
- Base: `aura_db`

### auth_db (PostgreSQL para autenticación)

- Nombre: `auth_db`
- Puerto: `5433` → dentro del contenedor es `5432`
- Usuario: `aura_root`
- Contraseña: `aura_password`
- Base: `auth_db`

### storage (MinIO — S3 compatible)

- Nombre: `storage`
- Puertos:
  - `9000` (API S3)
  - `9001` (Consola web)
- Usuario: `aura_root`
- Contraseña: `aura_password`

### memory_db (Redis)

- Nombre: `memory_db`
- Puerto: `6379`

### queue (RabbitMQ + Management UI)

- Nombre: `queue`
- Puertos:
  - `5672` (cola)
  - `15672` (panel web)
- Usuario: `aura_root`
- Contraseña: `aura_password`

### llm (Ollama)

- Nombre: `llm`
- Puerto: `11434`