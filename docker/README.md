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
