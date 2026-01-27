# Guía de Inicio Rápido - Aura Auth Service

## ⚡ 5 Minutos para Empezar

### Paso 1: Clonar y preparar el entorno

```bash
# Entrar al directorio del servicio
cd aura-auth-service

# Crear virtual environment
python -m venv venv

# Activar virtual environment
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
```

### Paso 2: Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 3: Configurar variables de entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env si es necesario
# (Usar valores por defecto para desarrollo local está bien)
```

### Paso 4: Verificar conectividad a la BD

Asegúrate de que PostgreSQL está corriendo:

```bash
# Si usas Docker Compose desde la raíz del proyecto:
cd ..
docker-compose -f docker/docker-compose.yml up -d auth-db

# Verificar que el contenedor está corriendo:
docker ps | grep auth-db
```

### Paso 5: Inicializar la base de datos

```bash
# Desde el directorio aura-auth-service
python init_db.py
```

Deberías ver algo como:

```
=== Inicializando Aura Auth Service ===

✓ Usuario administrador creado: admin
✓ Rol creado: admin
✓ Rol creado: user
✓ Rol creado: moderator
✓ Permiso creado: CREATE_USER
...

✓ Inicialización completada.
```

### Paso 6: Iniciar el servidor

```bash
cd app
python manage.py runserver 0.0.0.0:8000
```

Deberías ver:

```
Starting development server at http://0.0.0.0:8000/
Quit the server with CONTROL-C.
```

### Paso 7: Probar los endpoints

**En otra terminal:**

```bash
# Listar usuarios
curl http://localhost:8000/api/v1/admin/users

# Crear un usuario
curl -X POST http://localhost:8000/api/v1/admin/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "TestPass123!",
    "created_by_id": 1
  }'
```

## 🔍 Validar que todo funciona

### Con cURL:

```bash
# GET usuarios
curl http://localhost:8000/api/v1/admin/users

# GET roles
curl http://localhost:8000/api/v1/admin/roles
```

### Con REST Client (VS Code):

1. Instalar extensión "REST Client" por Huachao Mao
2. Abrir archivo [test.http](test.http)
3. Hacer click en "Send Request" sobre cualquier endpoint

## 📝 Respuestas esperadas

**Listar usuarios (200 OK):**
```json
{
    "success": true,
    "count": 1,
    "data": [
        {
            "id": 1,
            "username": "admin",
            "email": "admin@aura.com",
            "status": "active",
            "enabled": true,
            "roles": [],
            "created_at": "2024-01-01T10:00:00Z"
        }
    ]
}
```

## 🐛 Solucionar problemas

### Error: "Connection refused" (Base de datos)

```bash
# Verificar que PostgreSQL está corriendo
docker ps

# Si no está, iniciar:
docker-compose -f docker/docker-compose.yml up -d auth-db

# Verificar logs:
docker logs aura-backend-auth-db-1
```

### Error: "ModuleNotFoundError"

```bash
# Asegúrate de estar en el directorio correcto:
cd aura-auth-service

# Verificar que virtual environment está activado
which python  # Debe mostrar ruta a venv

# Si no, activar:
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### Error: "Port 8000 already in use"

```bash
# Usar otro puerto:
cd app
python manage.py runserver 0.0.0.0:8001
```

### Error: "No such table: auth_user"

```bash
# La BD no está inicializada. Ejecutar:
python init_db.py

# Verificar que init.sql fue ejecutado en la BD:
# (Esto lo hace Docker automáticamente)
docker exec aura-backend-auth-db-1 psql -U postgres -d auth_db -c "\dt"
```

## 📚 Próximos pasos

1. Leer [DOCUMENTATION.md](DOCUMENTATION.md) para entender la arquitectura
2. Revisar [test.http](test.http) para ver más ejemplos de endpoints
3. Modificar `.env` para ambiente de producción
4. Implementar autenticación JWT (ver DOCUMENTATION.md sección "Próximos Pasos")

## 🆘 Ayuda

- 📖 Ver [DOCUMENTATION.md](DOCUMENTATION.md) para documentación completa
- 🧪 Ver [test.http](test.http) para ejemplos de requests
- 💬 Revisar logs en `aura_auth.log`

---

¿Necesitas ayuda? Revisa la sección "Consideraciones de Seguridad" en la documentación.
