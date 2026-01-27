# Aura Auth Service

Servicio de administración de usuarios y roles para el ecosistema Aura.

## Descripción

Aura Auth Service es un servicio backend desarrollado en Django que proporciona:

- ✅ **Gestión de Usuarios**: Crear, actualizar, listar usuarios
- ✅ **Gestión de Roles**: Crear y listar roles
- ✅ **Asignación de Roles**: Asignar y remover roles de usuarios
- ✅ **Auditoría**: Registro completo de todas las operaciones
- ✅ **Seguridad**: Hashing de contraseñas, validación de entrada

## Tecnología

- **Framework**: Django 4.2 (LTS)
- **API**: Django REST Framework
- **Base de Datos**: PostgreSQL
- **Autenticación**: JWT (próximas fases)

## Inicio Rápido

### Requisitos
- Python 3.10+
- PostgreSQL 12+
- Docker (opcional)

### Instalación Local

```bash
# Crear virtual environment
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env

# Inicializar base de datos
python init_db.py

# Iniciar servidor
cd app
python manage.py runserver
```

El servidor estará disponible en `http://localhost:8000`

### Uso con Docker

```bash
# Con docker-compose (desde la raíz del proyecto)
docker-compose -f docker/docker-compose.yml up aura-auth-service
```

## Estructura del Proyecto

```
aura-auth-service/
├── app/                    # Código de la aplicación
│   ├── api/               # Controllers y rutas
│   ├── application/       # Servicios y excepciones
│   ├── configuration/     # Configuración de Django
│   ├── domain/            # Modelos y serializers
│   ├── infrastructure/    # Repositorios
│   └── manage.py          # CLI de Django
├── requirements.txt       # Dependencias Python
├── .env.example          # Variables de ejemplo
└── DOCUMENTATION.md      # Documentación completa
```

## Endpoints Disponibles

### Usuarios

```
POST   /api/v1/admin/users              # Crear usuario
GET    /api/v1/admin/users              # Listar usuarios
GET    /api/v1/admin/users/{id}         # Obtener usuario
POST   /api/v1/admin/users/{id}/assign_role  # Asignar rol
```

### Roles

```
POST   /api/v1/admin/roles              # Crear rol
GET    /api/v1/admin/roles              # Listar roles
GET    /api/v1/admin/roles/{id}         # Obtener rol
```

## Ejemplos

### Crear Usuario

```bash
curl -X POST http://localhost:8000/api/v1/admin/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jdoe",
    "email": "john@example.com",
    "password": "SecurePass123!",
    "created_by_id": 1
  }'
```

### Crear Rol

```bash
curl -X POST http://localhost:8000/api/v1/admin/roles \
  -H "Content-Type: application/json" \
  -d '{
    "name": "editor",
    "description": "Editor de contenido"
  }'
```

### Asignar Rol a Usuario

```bash
curl -X POST http://localhost:8000/api/v1/admin/users/2/assign_role \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": 1,
    "created_by_id": 1
  }'
```

## Documentación

Para documentación completa, ver [DOCUMENTATION.md](DOCUMENTATION.md) que incluye:

- Arquitectura general
- Decisiones técnicas
- Mapeo de base de datos
- Flujos de operación
- Consideraciones de seguridad
- Próximos pasos

## Variables de Entorno

```
DEBUG=True
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=auth_db
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
LOG_LEVEL=INFO
```

Copiar `.env.example` a `.env` y ajustar según el entorno.

## Próximas Fases

- [ ] Autenticación JWT
- [ ] Autorización basada en roles
- [ ] Más endpoints de administración
- [ ] Testing completo
- [ ] Monitoreo y observabilidad

## Licencia

Copyright © 2024 Aura. All rights reserved.

## Soporte

Para reportar bugs o sugerencias, usar GitHub Issues.
