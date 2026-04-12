# Aura Backend — Workspace Instructions

## Architecture

Monorepo con microservicios. Cada carpeta es un servicio independiente:

| Servicio | Tech | Puerto (dev) | Puerto (Docker) |
|---|---|---|---|
| `aura-auth-service/` | Django 5.x + DRF | 8000 | — |
| `aura-notification-service/` | Django | 8001 | 8002 |
| `aura-document-processing-service/` | FastAPI | — | 8000 |
| `aura-llm-service/` | FastAPI + LangGraph | — | 8001 |
| `mock-auth/` | Flask | — | 8080 |

Infraestructura Docker: PostgreSQL ×2, MinIO, Redis, RabbitMQ — ver [docker/docker-compose.yml](../docker/docker-compose.yml).

**Dos bases de datos separadas:**
- `auth_db`: puerto 5433 → datos de usuarios, RBAC
- `aura_db`: puerto 5432 → documentos, notificaciones

## Build & Run

```bash
# Todos los servicios
docker compose -f docker/docker-compose.yml up -d

# aura-auth-service (desarrollo local)
cd aura-auth-service
run.bat install    # instalar dependencias
run.bat setup      # migraciones + seed + superusuario
run.bat runserver  # servidor en :8000

# aura-notification-service (desarrollo local)
cd aura-notification-service
python manage.py runserver 8001
```

Documentación de setup detallada: [aura-auth-service/QUICKSTART.md](../aura-auth-service/QUICKSTART.md) y [aura-auth-service/SETUP.md](../aura-auth-service/SETUP.md).

## aura-auth-service — Admin de Django

El foco actual es la interfaz de administración. Ver [aura-auth-service/FILE_STRUCTURE.md](../aura-auth-service/FILE_STRUCTURE.md) para el mapa completo de archivos.

### Estructura modular del admin

```
accounts/
├── admin.py                 # Entry point — sólo importa los módulos
├── admin_parts/
│   ├── site_config.py       # Personalización del AdminSite (título, header, etc.)
│   ├── common.py            # Utilidades compartidas entre admins
│   ├── user_admin.py        # ModelAdmin para User
│   ├── rbac_admin.py        # Registros de modelos RBAC
│   ├── rbac/
│   │   ├── role_admin.py
│   │   ├── permission_admin.py
│   │   ├── user_role_admin.py
│   │   └── permission_in_role_admin.py
│   ├── forms/               # Formularios personalizados del admin
│   └── utils/               # Helpers de filtros, badges, etc.
├── models/
│   ├── user.py              # Custom User con UUID, soft delete, audit
│   ├── rbac.py              # Role, Permission, UserRole, PermissionInRole
│   └── audited.py           # Mixin base con campos de auditoría
└── admin/
    └── custom.css           # Estilos CSS del admin
```

### Patrones clave del admin

- **No editar `admin.py` directamente** — sólo agrega imports. Todo el código va en `admin_parts/`.
- **Status badges**: funciones helper en `admin_parts/utils/` que devuelven HTML con `format_html`.
- **Audit trail**: campos `created_by`, `updated_by`, `deleted_at`, `deleted_by` son `readonly_fields` siempre.
- **Soft delete**: los registros borrados tienen `deleted_at != NULL`; no se eliminan físicamente.
- **Permisos por rol**: super-admin ve campos extras y el audit trail completo; admin regular no.
- **Etiquetas en español**: `verbose_name` y `verbose_name_plural` en castellano en todos los modelos.

### Modelos RBAC

```python
User          # AUTH_USER_MODEL = 'accounts.User', UUID pk
Role          # name (unique)
Permission    # name (unique)
UserRole      # User ↔ Role con auditoría (through table)
PermissionInRole  # Role ↔ Permission (through table)
```

Funciones de utilidad: `user_has_permission(user, "nombre.permiso")`, `user_has_role(user, "NOMBRE_ROL")` — ver [aura-auth-service/accounts/utils.py](../aura-auth-service/accounts/utils.py).

## Convenciones generales

- **Variables de entorno**: `python-decouple` + archivo `.env` local (no se commitea).
- **Multi-DB routing**: configurado en `authservice/db_routers.py`; los modelos de `accounts` van a `auth_db`.
- **JWT**: tokens de acceso de 15 min, algoritmo HS256.
- **CORS**: por defecto solo `localhost:3000`; configurable en `.env`.
- **Tests**: `python manage.py test accounts` — hay 30+ tests en `accounts/tests.py`.

## Documentación existente

No duplicar — consultar directamente:
- [aura-auth-service/README.md](../aura-auth-service/README.md) — referencia completa (~1000 líneas)
- [aura-auth-service/IMPLEMENTATION_SUMMARY.md](../aura-auth-service/IMPLEMENTATION_SUMMARY.md) — decisiones de arquitectura
- [aura-auth-service/SHELL_EXAMPLES.md](../aura-auth-service/SHELL_EXAMPLES.md) — ejemplos de Django shell
- [documentation/db.mermaid](../documentation/db.mermaid) y `aut_db.mermaid` — esquemas de BD
