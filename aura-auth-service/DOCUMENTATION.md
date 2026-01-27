# DOCUMENTATION.md - Aura Auth Service

## 📋 Tabla de Contenidos
1. [Arquitectura General](#arquitectura-general)
2. [Decisiones Técnicas](#decisiones-técnicas)
3. [Mapeo de Base de Datos](#mapeo-de-base-de-datos)
4. [Flujos de Operación](#flujos-de-operación)
5. [Ejemplos de Requests y Responses](#ejemplos-de-requests-y-responses)
6. [Consideraciones de Seguridad](#consideraciones-de-seguridad)
7. [Próximos Pasos](#próximos-pasos)

---

## Arquitectura General

### Descripción

Aura Auth Service es un **servicio de administración de usuarios y roles** desarrollado en Django con PostgreSQL. Está diseñado para ser la columna vertebral de un sistema de autenticación y autorización empresarial.

### Estructura en Capas

```
┌─────────────────────────────────────────────────────┐
│           REST API (DRF)                            │
│  Controllers/ViewSets - Manejo de Requests          │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│       Application Layer (Servicios)                 │
│  UserService, RoleService, UserRoleService          │
│  - Lógica de negocio                                │
│  - Orquestación                                     │
│  - Auditoría                                        │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│   Infrastructure Layer (Repositorios)               │
│  UserRepository, RoleRepository                     │
│  - Acceso a datos                                   │
│  - Manejo de IntegrityErrors                        │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│       Domain Layer (Modelos & DTOs)                 │
│  AuthUser, Role, AuthUserInRole, Permission         │
│  Serializers para validación y transformación       │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│      PostgreSQL Database (managed=False)            │
│  Tablas existentes, sin migraciones                 │
└─────────────────────────────────────────────────────┘
```

### Componentes Principales

#### 1. **Models** (`domain/models/`)
- `AuthUser`: Representa usuarios en el sistema
- `Role`: Representa roles de acceso
- `AuthUserInRole`: Relación M2M entre usuarios y roles
- `Permission`: Representa permisos del sistema
- `PermissionInRole`: Relación M2M entre roles y permisos

#### 2. **Serializers** (`domain/dtos/`)
- Validación de entrada
- Transformación de datos
- Documentación de API

#### 3. **Services** (`application/services/`)
- `UserService`: Lógica de creación/actualización de usuarios
- `RoleService`: Lógica de gestión de roles
- `UserRoleService`: Lógica de asignación de roles

#### 4. **Repositories** (`infrastructure/persistence/`)
- `UserRepository`: Acceso a datos de usuarios
- `RoleRepository`: Acceso a datos de roles
- `UserRoleRepository`: Acceso a asignaciones

#### 5. **Controllers** (`api/controllers/`)
- `UserViewSet`: Endpoints REST para usuarios
- `RoleViewSet`: Endpoints REST para roles

---

## Decisiones Técnicas

### 1. **Django con `managed = False`**
- ✅ Respeta la estructura existente de BD
- ✅ No crea migraciones automáticas
- ✅ Permite trabajar con esquema existente
- ⚠️ Requiere sincronización manual de cambios

```python
class Meta:
    db_table = 'auth_user'
    managed = False  # ← No gestiona cambios de esquema
```

### 2. **Patrón de Repositorio**
- **Ventaja**: Aislamiento de lógica de acceso a datos
- **Implementación**: Una clase por entidad
- **Manejo de errores**: Conversión de excepciones de BD a excepciones de aplicación

```python
# Ejemplo: UserRepository
@staticmethod
def create(username, email, password_hash, created_by_id):
    try:
        return AuthUser.objects.create(...)
    except IntegrityError as e:
        raise IntegrityException(...)
```

### 3. **Servicios de Negocio**
- **Responsabilidad**: Orquestación y lógica
- **Auditoría**: Logging en cada operación
- **Transacciones**: Manejo de datos consistentes

```python
def create_user(username, email, password, created_by_id):
    password_hash = make_password(password)
    return UserRepository.create(...)
```

### 4. **Hashing de Contraseñas**
- **Algoritmo**: Django's `make_password()` (PBKDF2 por defecto)
- **Alternativa**: BCrypt (disponible en `requirements.txt`)
- **Nunca**: Almacenar en texto plano

### 5. **Campos de Auditoría Obligatorios**
Cada tabla tiene campos de auditoría:
- `created_by`: Usuario que crea el registro
- `created_at`: Timestamp de creación
- `updated_by`: Usuario que actualiza
- `updated_at`: Timestamp de actualización
- `deleted_by`: Usuario que elimina (soft delete)
- `deleted_at`: Timestamp de eliminación (soft delete)

### 6. **Soft Deletes**
En lugar de eliminar registros, se marca `deleted_at`:
```python
# Eliminar rol de usuario (soft delete)
assignment.deleted_at = timezone.now()
assignment.deleted_by_id = user_id
assignment.save()
```

---

## Mapeo de Base de Datos

### Tabla: `auth_user`

| Campo | Tipo | Mapeo Django | Descripción |
|-------|------|--------------|-------------|
| `id` | SERIAL | `AutoField` | PK autoincrementado |
| `username` | VARCHAR(255) | `CharField(unique=True)` | Identificador único |
| `email` | VARCHAR(255) | `EmailField(unique=True)` | Email único |
| `password` | VARCHAR(255) | `CharField` | Hash de contraseña |
| `status` | ENUM('active', 'inactive') | `CharField(choices=...)` | Estado del usuario |
| `enabled` | BOOLEAN | `BooleanField` | Usuario habilitado |
| `created_by` | BIGINT (FK) | `ForeignKey(AuthUser)` | Auditoría |
| `created_at` | TIMESTAMP | `DateTimeField(auto_now_add=True)` | Auditoría |

### Tabla: `role`

| Campo | Tipo | Mapeo Django | Descripción |
|-------|------|--------------|-------------|
| `id` | SERIAL | `AutoField` | PK autoincrementado |
| `name` | VARCHAR(255) | `CharField(unique=True)` | Nombre del rol |
| `description` | VARCHAR(255) | `CharField` | Descripción |

### Tabla: `auth_user_in_role`

| Campo | Tipo | Mapeo Django | Descripción |
|-------|------|--------------|-------------|
| `id` | SERIAL | `AutoField` | PK autoincrementado |
| `auth_user_id` | BIGINT (FK) | `ForeignKey(AuthUser)` | Usuario |
| `role_id` | BIGINT (FK) | `ForeignKey(Role)` | Rol |
| `created_by` | BIGINT (FK) | `ForeignKey(AuthUser)` | Auditoría |
| `created_at` | DATE | `DateField(auto_now_add=True)` | Auditoría |
| `deleted_by` | BIGINT (FK) | `ForeignKey(AuthUser, null=True)` | Soft delete |
| `deleted_at` | TIMESTAMP | `DateTimeField(null=True)` | Soft delete |

**Relación única**: `UNIQUE(auth_user_id, role_id)` previene duplicados

### Tabla: `permission` y `permission_in_role`

Estructura similar para gestión de permisos asociados a roles.

---

## Flujos de Operación

### 1. Crear Usuario

**Flujo Detallado:**

```
POST /api/v1/admin/users
│
├─ [1] UserCreateRequestSerializer.validate()
│   ├─ Validar username: longitud, formato
│   ├─ Validar email: formato válido, no duplicado
│   └─ Validar password: mín 8 caracteres
│
├─ [2] UserService.create_user()
│   ├─ make_password(password) → Hash bcrypt/PBKDF2
│   ├─ UserRepository.create()
│   │   └─ AuthUser.objects.create(
│   │       username, email, password_hash,
│   │       status='active', enabled=True, ...
│   │     )
│   └─ logger.info("Usuario creado: ID {user.id}")
│
└─ [3] Respuesta 201 Created
    {
        "success": true,
        "data": {...user...}
    }
```

**Estados Finales del Usuario:**
- ✅ `status` = `active`
- ✅ `enabled` = `true`
- ✅ `account_non_expired` = `true`
- ✅ `account_non_locked` = `true`
- ✅ `credentials_non_expired` = `true`
- ✅ `failed_login_attempts` = `0`

### 2. Crear Rol

**Flujo Detallado:**

```
POST /api/v1/admin/roles
│
├─ [1] RoleCreateRequestSerializer.validate()
│   ├─ Validar name: no duplicado
│   └─ Validar description: no vacío
│
├─ [2] RoleService.create_role()
│   ├─ RoleRepository.create()
│   │   └─ Role.objects.create(name, description)
│   └─ logger.info("Rol creado: ID {role.id}")
│
└─ [3] Respuesta 201 Created
    {
        "success": true,
        "data": {...role..., "permissions": []}
    }
```

### 3. Asignar Rol a Usuario

**Flujo Detallado:**

```
POST /api/v1/admin/users/{user_id}/assign_role
│
├─ [1] UserRoleAssignmentRequestSerializer.validate()
│   └─ Validar role_id existe
│
├─ [2] UserRoleService.assign_role_to_user()
│   │
│   ├─ UserRepository.get_by_id(user_id)
│   │   └─ Si no existe → UserNotFoundException
│   │
│   ├─ RoleRepository.get_by_id(role_id)
│   │   └─ Si no existe → RoleNotFoundException
│   │
│   ├─ Verificar no esté ya asignado
│   │   └─ Si existe → RoleAlreadyAssignedException
│   │
│   ├─ UserRoleRepository.assign_role()
│   │   └─ AuthUserInRole.objects.create(
│   │       auth_user_id, role_id, created_by_id
│   │     )
│   │
│   └─ logger.info("Rol asignado: ID {assignment.id}")
│
└─ [3] Respuesta 201 Created
    {
        "success": true,
        "data": {
            "id": 1,
            "user": {...},
            "role": {...},
            "created_at": "2024-01-01T10:00:00Z"
        }
    }
```

---

## Ejemplos de Requests y Responses

### Crear Usuario

**Request:**
```http
POST /api/v1/admin/users HTTP/1.1
Content-Type: application/json

{
    "username": "jdoe",
    "email": "john.doe@example.com",
    "password": "SecurePassword123!",
    "created_by_id": 1
}
```

**Response (201 Created):**
```json
{
    "success": true,
    "data": {
        "id": 2,
        "username": "jdoe",
        "email": "john.doe@example.com",
        "status": "active",
        "status_display": "Activo",
        "enabled": true,
        "last_login": null,
        "created_at": "2024-01-01T10:30:00Z",
        "updated_at": "2024-01-01T10:30:00Z"
    }
}
```

**Errores Posibles:**

```json
// 400 Bad Request - Email ya existe
{
    "success": false,
    "error": {
        "email": ["Este correo electrónico ya está registrado."]
    },
    "status_code": 400
}

// 400 Bad Request - Password muy corta
{
    "success": false,
    "error": {
        "password": ["La contraseña debe tener al menos 8 caracteres."]
    },
    "status_code": 400
}
```

### Listar Usuarios

**Request:**
```http
GET /api/v1/admin/users HTTP/1.1
```

**Response (200 OK):**
```json
{
    "success": true,
    "count": 2,
    "data": [
        {
            "id": 1,
            "username": "admin",
            "email": "admin@aura.com",
            "status": "active",
            "status_display": "Activo",
            "enabled": true,
            "roles": [
                {
                    "id": 1,
                    "name": "admin"
                }
            ],
            "created_at": "2024-01-01T10:00:00Z"
        },
        {
            "id": 2,
            "username": "jdoe",
            "email": "john.doe@example.com",
            "status": "active",
            "status_display": "Activo",
            "enabled": true,
            "roles": [],
            "created_at": "2024-01-01T10:30:00Z"
        }
    ]
}
```

### Crear Rol

**Request:**
```http
POST /api/v1/admin/roles HTTP/1.1
Content-Type: application/json

{
    "name": "editor",
    "description": "Editor de contenido"
}
```

**Response (201 Created):**
```json
{
    "success": true,
    "data": {
        "id": 3,
        "name": "editor",
        "description": "Editor de contenido",
        "permissions": []
    }
}
```

### Listar Roles

**Request:**
```http
GET /api/v1/admin/roles HTTP/1.1
```

**Response (200 OK):**
```json
{
    "success": true,
    "count": 3,
    "data": [
        {
            "id": 1,
            "name": "admin",
            "description": "Administrador del sistema"
        },
        {
            "id": 2,
            "name": "user",
            "description": "Usuario normal"
        },
        {
            "id": 3,
            "name": "editor",
            "description": "Editor de contenido"
        }
    ]
}
```

### Asignar Rol a Usuario

**Request:**
```http
POST /api/v1/admin/users/2/assign_role HTTP/1.1
Content-Type: application/json

{
    "role_id": 3,
    "created_by_id": 1
}
```

**Response (201 Created):**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "user": {
            "id": 2,
            "username": "jdoe",
            "email": "john.doe@example.com",
            "status": "active",
            "enabled": true,
            "created_at": "2024-01-01T10:30:00Z",
            "updated_at": "2024-01-01T10:30:00Z"
        },
        "role": {
            "id": 3,
            "name": "editor",
            "description": "Editor de contenido"
        },
        "created_at": "2024-01-01T11:00:00Z"
    }
}
```

**Errores Posibles:**

```json
// 400 Bad Request - Rol ya asignado
{
    "success": false,
    "error": "El usuario ya tiene asignado este rol.",
    "status_code": 400
}

// 404 Not Found - Usuario no existe
{
    "success": false,
    "error": "Usuario no encontrado.",
    "status_code": 404
}

// 404 Not Found - Rol no existe
{
    "success": false,
    "error": "Rol no encontrado.",
    "status_code": 404
}
```

---

## Consideraciones de Seguridad

### 1. **Hashing de Contraseñas**
✅ **Implementado:**
- Uso de `Django.contrib.auth.hashers.make_password()`
- Algoritmo PBKDF2 (2 iteraciones por defecto)
- Nunca se almacenan en texto plano

⚠️ **Mejoras pendientes:**
```python
# Considerar BCrypt para mayor seguridad
from bcrypt import hashpw, gensalt
password_hash = hashpw(password.encode(), gensalt(rounds=12))
```

### 2. **Validación de Entrada**
✅ **Implementado:**
- Validación de username (unicidad)
- Validación de email (formato + unicidad)
- Validación de password (mín 8 caracteres)

⚠️ **Recomendaciones:**
```python
# Agregar complejidad de password
import re

def validate_password_strength(password):
    if len(password) < 8:
        raise ValidationError("Mínimo 8 caracteres")
    if not re.search(r'[A-Z]', password):
        raise ValidationError("Debe contener mayúscula")
    if not re.search(r'[a-z]', password):
        raise ValidationError("Debe contener minúscula")
    if not re.search(r'[0-9]', password):
        raise ValidationError("Debe contener número")
    if not re.search(r'[!@#$%^&*]', password):
        raise ValidationError("Debe contener carácter especial")
```

### 3. **Auditoría**
✅ **Implementado:**
- Logging de todas las operaciones principales
- Campos `created_by`, `updated_by`, `deleted_by`
- Timestamps de todas las acciones

### 4. **Soft Deletes**
✅ **Implementado:**
- Los registros se marcan como deletados, no se eliminan
- Permite auditoría completa
- Previene pérdida de integridad referencial

### 5. **Integridad de Datos**
✅ **Implementado:**
- Validación de FK existentes antes de crear relaciones
- Manejo de `IntegrityError` para operaciones de BD
- Conversión a excepciones de aplicación

### 6. **Recomendaciones Adicionales para Producción**

**CORS:**
```python
# En settings.py - Especificar dominios
CORS_ALLOWED_ORIGINS = [
    "https://app.example.com",
    "https://admin.example.com",
]
```

**HTTPS:**
```python
# En settings.py - Requerer HTTPS
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

**Rate Limiting:**
```python
# Instalar: pip install djangorestframework-throttling
from rest_framework.throttling import UserRateThrottle

class UserThrottle(UserRateThrottle):
    scope = 'user'
    THROTTLE_RATES = {'user': '100/hour'}
```

**JWT para Autenticación:**
```python
# Instalar: pip install djangorestframework-simplejwt
from rest_framework_simplejwt.authentication import JWTAuthentication

class UserViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
```

---

## Próximos Pasos

### Fase 2: Autenticación y Autorización
- [ ] Implementar JWT (JSON Web Tokens)
- [ ] Crear endpoint de login
- [ ] Crear endpoint de refresh token
- [ ] Implementar logout
- [ ] Agregar `IsAuthenticated` a los endpoints

**Ejemplo:**
```python
from rest_framework.permissions import IsAuthenticated

class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def create(self, request):
        # Solo usuarios autenticados pueden crear
        pass
```

### Fase 3: Autorización basada en Roles
- [ ] Implementar middlewares de autorización
- [ ] Crear permisos por recurso
- [ ] Vincular permisos con roles
- [ ] Verificar permisos en endpoints

**Ejemplo:**
```python
from rest_framework.permissions import BasePermission

class HasCreateUserPermission(BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('CREATE_USER')

class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasCreateUserPermission]
```

### Fase 4: Endpoints Adicionales
- [ ] PUT /admin/users/{id} - Actualizar usuario
- [ ] DELETE /admin/users/{id} - Eliminar usuario (soft delete)
- [ ] POST /admin/users/{id}/remove_role - Remover rol
- [ ] GET /admin/users/{id}/roles - Listar roles de usuario
- [ ] PUT /admin/roles/{id} - Actualizar rol
- [ ] DELETE /admin/roles/{id} - Eliminar rol
- [ ] GET /admin/roles/{id}/permissions - Listar permisos del rol
- [ ] POST /admin/roles/{id}/permissions - Agregar permiso a rol

### Fase 5: Monitoreo y Observabilidad
- [ ] Integrar Prometheus para métricas
- [ ] Agregar trazabilidad distribuida (OpenTelemetry)
- [ ] Configurar alertas en Sentry
- [ ] Dashboard de Grafana

### Fase 6: Testing
- [ ] Unit tests para servicios
- [ ] Integration tests para repositorios
- [ ] E2E tests para endpoints
- [ ] Load testing con Locust

**Estructura de tests:**
```
tests/
├── unit/
│   ├── test_user_service.py
│   ├── test_role_service.py
│   └── test_user_role_service.py
├── integration/
│   ├── test_user_repository.py
│   └── test_role_repository.py
└── e2e/
    ├── test_user_api.py
    └── test_role_api.py
```

---

## Instalación y Ejecución

### Prerrequisitos
- Python 3.10+
- PostgreSQL 12+
- Docker (opcional)

### Instalación Local

```bash
# 1. Clonar proyecto
cd aura-auth-service

# 2. Crear virtual environment
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con credenciales reales

# 5. Ejecutar inicialización
python init_db.py

# 6. Iniciar servidor
cd app
python manage.py runserver 0.0.0.0:8000
```

### Con Docker

```bash
# Construir imagen
docker build -t aura-auth-service .

# Ejecutar contenedor
docker run -p 8000:8000 \
  -e DATABASE_HOST=auth-db \
  -e DATABASE_PORT=5432 \
  aura-auth-service
```

### Verificar que funciona

```bash
# Listar usuarios
curl http://localhost:8000/api/v1/admin/users

# Crear usuario
curl -X POST http://localhost:8000/api/v1/admin/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test",
    "email": "test@example.com",
    "password": "TestPass123!",
    "created_by_id": 1
  }'
```

---

## Estructura de Directorios Final

```
aura-auth-service/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── controllers/
│   │   │   ├── __init__.py
│   │   │   └── controllers.py          # ViewSets REST
│   │   └── urls.py                     # Rutas de API
│   │
│   ├── application/
│   │   ├── exceptions/
│   │   │   ├── __init__.py
│   │   │   └── exceptions.py           # Excepciones personalizadas
│   │   └── services/
│   │       ├── __init__.py
│   │       └── services.py             # Lógica de negocio
│   │
│   ├── configuration/
│   │   ├── __init__.py
│   │   ├── settings.py                 # Configuración Django
│   │   ├── environment_variables.py    # Variables de entorno
│   │   ├── logging_configuration.py    # Configuración de logs
│   │   ├── exception_handler.py        # Manejo global de excepciones
│   │   ├── urls.py                     # URLs raíz
│   │   └── wsgi.py                     # WSGI
│   │
│   ├── domain/
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── models.py               # Modelos Django
│   │   └── dtos/
│   │       ├── __init__.py
│   │       └── serializers.py          # Serializers DRF
│   │
│   ├── infrastructure/
│   │   └── persistence/
│   │       ├── repositories/
│   │       │   ├── __init__.py
│   │       │   └── repositories.py     # Acceso a datos
│   │       └── __init__.py
│   │
│   ├── __init__.py
│   └── manage.py                       # CLI de Django
│
├── requirements.txt                    # Dependencias Python
├── .env.example                        # Ejemplo de variables
├── init_db.py                          # Inicialización BD
├── manage.py                           # Wrapper de manage.py
└── DOCUMENTATION.md                    # Esta documentación
```

---

## Contacto y Soporte

Para consultas o problemas, dirigirse a:
- **Email**: dev@aura.com
- **Issues**: GitHub Issues del proyecto
- **Wiki**: Documentación en GitHub Wiki

---

**Última actualización:** 26 de enero de 2026
**Versión:** 1.0.0
**Estado:** Producción
