# Documentación - Estructura y recomendaciones del servicio de autenticación

Este documento describe la estructura de carpetas propuesta para `aura-auth-service`, las responsabilidades de cada componente y recomendaciones para su desarrollo y despliegue.

## Objetivo
Servicio de autenticación: gestión de usuarios, emisión/validación de JWT, integración LDAP, roles/permissions, y endpoints para login/registro/gestión de cuentas.

## Estructura recomendada (carpetas principales)

- `aura_auth/` — Paquete del proyecto Django
  - `settings/` — Configuración por entorno (base.py, dev.py, prod.py)
  - `urls/` — Enrutado modular (api, admin, health)
  - `wsgi/` y `asgi/` — Entrypoints de despliegue

- `users/` — App para modelos y administración de usuarios
  - `admin/` — Configuración del admin y paneles personalizados
  - `migrations/` — Migraciones Django
  - `serializers/` — Serializadores (si se usa DRF)
  - `views/` — Vistas/Controladores para gestión de cuentas
  - `services/` — Lógica de negocio (creación/activación/recuperación)
  - `tests/` — Tests unitarios e integración
  - `management/commands` — Comandos custom (ej. crear superuser por env)

- `authentication/` — Endpoint y lógica de autenticación (tokens)
  - `tokens/` — Implementaciones JWT, refresco, blacklist
  - `views/` — Endpoints: `/login`, `/logout`, `/refresh`, `/verify`
  - `serializers/`, `services/`, `tests/`

- `ldap_integration/` — Adaptadores e integraciones con LDAP/AD
  - `adapters/` — Conectores y mapeos de atributos
  - `services/` — Reglas para fallback y sincronización

- `roles/` & `permissions/` — Gestión de roles y políticas
  - `services/` — CRUD de roles, asignación de permisos

- `infrastructure/` — Persistencia, repositorios y migraciones especiales

- `configuration/` — Gestión de variables de entorno, carga segura (dotenv, secret manager)

- `templates/` — Emails (activación, recuperación), páginas del admin personalizadas
- `static/` — Recursos estáticos del admin/custom UI
- `tests/` — Suite global de integración y contrato entre microservicios
- `docs/` — Documentación adicional y diagramas
- `documentation/README.md` — (este archivo)

