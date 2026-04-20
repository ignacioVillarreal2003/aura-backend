# Visión general del servicio

## Qué hace este servicio

API **FastAPI** orientada a la **ingesta**, **almacenamiento**, **procesamiento** y **consulta** de documentos y sus fragmentos (incluida vectorización y enriquecimiento según la configuración del despliegue). Las operaciones pesadas suelen apoyarse en **colas de mensajes** y en **almacenamiento de objetos**, además de **PostgreSQL** para metadatos y estado.

## Prefijo de la API

Todas las rutas de negocio bajo el router principal comparten el prefijo **`/api`**. La aplicación también expone documentación y métricas en rutas raíz o bajo `/api` según corresponda.

## CORS

Los orígenes permitidos se configuran con la variable de entorno **`CORS_ORIGINS`** (lista). En entornos de desarrollo es habitual permitir orígenes amplios; en producción conviene restringirlos al front y a los orígenes que consuman la API.

## Métricas

La aplicación instrumenta **Prometheus** y expone métricas en **`/metrics`**. Esa ruta está **excluida de la autenticación** del middleware de la API para facilitar el scraping por parte del monitor.

## Configuración y arranque

El comportamiento (lectores, splitters, embedders, URLs de otros servicios, credenciales de base de datos, MinIO, RabbitMQ, etc.) depende de variables de entorno. Un ejemplo de conjunto típico en Docker está en **`.env.docker`** en la raíz del servicio; no se reproduce aquí la tabla completa para evitar desalineación con el código.

## Contrato HTTP

Los paths exactos, cuerpos y respuestas están definidos en **OpenAPI** (`/api/openapi.json`) y en **Swagger** (`/api/docs`) / **ReDoc** (`/api/redoc`).
