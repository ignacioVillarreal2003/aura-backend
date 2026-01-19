# READMEINI - Implementación inicial y cómo testear

## Resumen de lo que implementé

- Creé una **instancia mínima de un proyecto Django** dentro de `aura-auth-service`:
  - `manage.py`
  - `aura_auth/` con `settings.py`, `urls.py`, `wsgi.py`, `asgi.py` (configuración mínima)
  - App `users/` con `apps.py`, `admin.py` (registrado `User` con `UserAdmin`), `models.py` y `migrations/__init__.py`.
- Añadí archivos de soporte:
  - `requirements.txt` (Django, psycopg2, python-dotenv, gunicorn)
  - `.env.example` con variables para conectar a `auth_db` (por defecto pensadas para ejecutar `auth_db` en Docker y conectar desde el host en `localhost:5433`).
- Configuré el **admin de Django** para permitir crear/gestionar usuarios (por ahora usamos el modelo `User` incorporado).
- Documenté los pasos iniciales en este archivo para que puedas levantar y testear el servicio desde la terminal.

---

## Cómo levantar todo para testear (paso a paso)

> Estas instrucciones asumen que usarás la base `auth_db` definida en `docker/auth-db` y que ejecutarás el servicio Django desde la terminal (virtualenv), tal como pediste.

### 1) Levantar la base de datos (Docker)

- Desde la raíz del repo, inicia el servicio `auth_db` con docker-compose:

```bash
docker-compose up -d auth_db
```

- Verifica que el contenedor esté sano:

```bash
docker-compose ps auth_db
# o
docker logs auth_db --tail 50
```

- Si necesitas conectarte desde el host para comprobar tablas:

```bash
docker-compose exec auth_db psql -U aura_root -d auth_db -c "SELECT 1"
```

> Nota: `docker/auth-db` en Compose expone el puerto `5433` en el host (mapea a `5432` del contenedor). Por eso en `.env.example` el valor por defecto de `DB_HOST` es `localhost` y `DB_PORT` `5433` para pruebas locales.

### 2) Preparar entorno Python e instalar dependencias

- Crear y activar virtualenv (Windows):

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

- Copia el archivo de ejemplo de variables de entorno y revisa los valores:

```powershell
copy .env.example .env
# Edita .env si es necesario (DB_HOST/DB_PORT)
```

La aplicación usa `python-dotenv` para cargar `.env` automáticamente.

### 3) Aplicar migraciones

```bash
python manage.py migrate
```

Esto creará las tablas del auth y otras tablas necesarias en `auth_db`.

### 4) Crear un superusuario (para acceder al admin)

```bash
python manage.py createsuperuser
```

Sigue las instrucciones interactivas para completar `username`, `email` y `password`.

### 5) Levantar el servidor y probar el admin

```bash
python manage.py runserver 0.0.0.0:8000
```

Abrir en el navegador: `http://localhost:8000/admin/` y entrar con el superusuario. Desde ahí podrás crear usuarios, asignar permisos y comprobar que se guardan en la BD.

---

## Comprobaciones útiles y debugging

- Si `python manage.py migrate` falla con error de conexión:
  - Verifica que `auth_db` esté corriendo (`docker-compose ps auth_db`).
  - Revisa `DB_HOST`/`DB_PORT` en `.env`; si usas el contenedor con puerto mapeado al host, usa `localhost:5433`.
  - Intenta conectarte con `psql` desde el contenedor para confirmar credenciales.

- Para listar usuarios desde la DB:

```bash
docker-compose exec auth_db psql -U aura_root -d auth_db -c "SELECT id, username, email FROM auth_user;"
```

- Si necesitas ejecutar comandos dentro del entorno del proyecto usando Docker (si prefieres no usar virtualenv):
  - Puedes `docker run --rm -v %CD%:/app -w /app python:3.11-slim bash -lc "pip install -r requirements.txt && python manage.py migrate && python manage.py createsuperuser"`

---

## Qué probamos en estos pasos

- Que la **BD `auth_db`** esté operativa y accesible desde el host.
- Que Django pueda **aplicar migraciones** en esa BD.
- Que el **admin** funcione y permita **crear usuarios** que queden persistidos en `auth_db`.

---

## Siguientes pasos sugeridos (puedo implementarlos)

- Añadir endpoints REST para login/refresh/logout (DRF + JWT) y tests.
- Implementar un comando/entrypoint que cree un superusuario a partir de variables de entorno para entornos de CI/CD.
- Añadir tests unitarios e integración del flujo de autenticación.

---

Si querés, te doy los comandos exactos para automatizar la creación del superusuario desde variables de entorno o procedo a implementar los endpoints REST ahora mismo. Indica cuál prefieres.