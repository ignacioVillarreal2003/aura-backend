# Docker

## Levantar todo el stack (CPU + observabilidad)

Desde la carpeta `docker` del repo:

```powershell
docker compose `
  -f docker-compose/docker-compose-infrastructure.yml `
  -f docker-compose/docker-compose-services.yml `
  -f docker-compose/docker-compose-observability.yml `
  up -d
```

Desde la raíz `aura-backend`:

```powershell
docker compose `
  -f docker/docker-compose/docker-compose-infrastructure.yml `
  -f docker/docker-compose/docker-compose-services.yml `
  -f docker/docker-compose/docker-compose-observability.yml `
  up -d
```

Orden recomendado de los `-f`: primero infra, después servicios de aplicación, por último observabilidad. Se fusionan en un solo proyecto y los `depends_on` cruzan entre ficheros.

Para bajar todo lo levantado con esos mismos ficheros, usá `down` en lugar de `up -d` (misma lista de `-f`).

## Stack con GPU

Sustituí `docker-compose-services.yml` por `docker-compose-services.gpu.yml` (con o sin observabilidad, según necesites):

```powershell
docker compose `
  -f docker-compose/docker-compose-infrastructure.yml `
  -f docker-compose/docker-compose-services.gpu.yml `
  -f docker-compose/docker-compose-observability.yml `
  up -d
```

## Migraciones de base de datos (aura-db)

El esquema de `aura-db` vive en `database/aura-db/document_processing.sql`, que **solo se ejecuta al
inicializar un volumen nuevo**. Para una base de datos **ya existente** hay que aplicar a mano
los scripts de `database/aura-db/migrations/` (son idempotentes: usan `IF NOT EXISTS`).

Capa de artefactos (`artifact`, `artifact_version`, `message_artifact`, tablas `course`/`quiz`/
`timeline`/`lessons_learned` y columnas `report.artifact_id` / `checklist.artifact_id`):

```powershell
# Contra el contenedor de la base ya levantada
docker exec -i aura-db psql -U $env:DB_USER -d $env:DB_NAME `
  -f /docker-entrypoint-initdb.d/migrations/0001_artifacts.sql
```

> Si el archivo no está montado dentro del contenedor, copialo primero
> (`docker cp database/aura-db/migrations/0001_artifacts.sql aura-db:/tmp/`) o redirigí el
> contenido por stdin: `Get-Content database/aura-db/migrations/0001_artifacts.sql | docker exec -i aura-db psql -U $env:DB_USER -d $env:DB_NAME`.

En instalaciones nuevas no hace falta nada: `document_processing.sql` ya incluye estas tablas.

### Permisos de artefactos (auth-db)

Para que los usuarios puedan llamar a `/api/v1/artifacts/`, hay que otorgar los permisos nuevos
en `auth-db`. En **instalaciones nuevas** `data.sql` ya los incluye (superadmin/admin: todos;
rol `user`: todos menos `MANAGE_ARTIFACTS`). En una **auth-db existente**, aplicá la migración:

```powershell
Get-Content database/auth-db/migrations/0001_artifact_permissions.sql | `
  docker exec -i auth-db psql -U $env:AUTH_DB_USER -d $env:AUTH_DB_NAME
```

Los usuarios deben reloguear (o refrescar su token) para que los nuevos permisos aparezcan en el JWT.
