# Aura Authentication Service

A Django-based authentication microservice for semi-microservices architecture using PostgreSQL.

## Sprint 1: Foundations

This is the initial implementation focusing on core functionality:
- Custom User model with UUID primary keys
- Role-Based Access Control (RBAC)
- Permission management
- Soft delete support
- Complete audit trail

**No JWT, no login endpoints, Django core only.**

## Architecture

- **Framework**: Django 5.x
- **Python**: 3.13
- **Database**: PostgreSQL 17
- **Database Driver**: psycopg2-binary

## Project Structure

```
aura-auth-service/
├── manage.py                 # Django management script
├── requirements.txt          # Python dependencies
├── .env                      # Environment configuration
├── README.md                 # This file
│
├── authservice/              # Main Django project
│   ├── settings.py          # Django settings (PostgreSQL, apps)
│   ├── urls.py              # URL routing
│   ├── wsgi.py              # WSGI application
│   ├── asgi.py              # ASGI application
│   └── __init__.py
│
├── accounts/                 # RBAC application
│   ├── models.py            # User, Role, Permission, relationships
│   ├── admin.py             # Django admin customization
│   ├── apps.py              # App configuration
│   ├── migrations/          # Database migrations
│   └── __init__.py
│
└── scripts/
    └── setup_db.py          # Database initialization script
```

## Database Models

### Core Models

#### **User** (Custom)
- `id` (UUID, PK)
- `username` (Unique, indexed)
- `email` (Unique, indexed)
- `password_hash` (Hashed)
- `is_active` (Boolean)
- `is_staff` (Boolean)
- `is_superuser` (Boolean)
- Audit fields: `created_at`, `created_by`, `updated_at`, `updated_by`, `deleted_at`, `deleted_by`

#### **Role**
- `id` (UUID, PK)
- `name` (Unique, indexed)
- `description` (Text)
- Audit fields: `created_at`, `created_by`, `updated_at`, `updated_by`, `deleted_at`, `deleted_by`

#### **Permission**
- `id` (UUID, PK)
- `code` (Unique, indexed) - e.g., "user.create", "role.delete"
- `description` (Text)
- Audit fields: `created_at`, `created_by`, `updated_at`, `updated_by`, `deleted_at`, `deleted_by`

### Relationship Models

#### **UserRole**
- `id` (UUID, PK)
- `user` (FK → User)
- `role` (FK → Role)
- `assigned_at` (Timestamp)
- `assigned_by` (String)

#### **RolePermission**
- `id` (UUID, PK)
- `role` (FK → Role)
- `permission` (FK → Permission)
- `granted_at` (Timestamp)
- `granted_by` (String)

## Features

### Audit Fields
All models include comprehensive audit tracking:
- `created_at`: Auto-set on creation
- `created_by`: Username of creator
- `updated_at`: Auto-updated on modification
- `updated_by`: Username of updater
- `deleted_at`: Soft delete timestamp (NULL = active)
- `deleted_by`: Username of deleter

### Soft Delete
Records are never hard-deleted; instead, `deleted_at` is set. Queries should filter out soft-deleted records.

```python
# Get only active records
active_users = User.objects.filter(deleted_at__isnull=True)

# Soft delete a user
user.soft_delete(deleted_by="admin")

# Restore a soft-deleted user
user.restore()

# Check if deleted
if user.is_deleted:
    print("This user is deleted")
```

### UUID Primary Keys
All entities use UUID instead of sequential integers for better security and multi-database compatibility.

### Constraints
- Unique username (active users only)
- Unique email (active users only)
- Unique role name (active roles only)
- Unique permission code (active permissions only)

## Setup Instructions

### 1. Prerequisites

- Python 3.13+
- PostgreSQL 17+
- pip

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Edit `.env` file with your PostgreSQL credentials:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here

DB_ENGINE=django.db.backends.postgresql
DB_NAME=aura_auth_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### 5. Create PostgreSQL Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE aura_auth_db;
CREATE USER aura_user WITH PASSWORD 'secure_password';
ALTER ROLE aura_user SET client_encoding TO 'utf8';
ALTER ROLE aura_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE aura_user SET default_transaction_deferrable TO on;
ALTER ROLE aura_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE aura_auth_db TO aura_user;
\q
```

Or update `.env`:
```env
DB_USER=aura_user
DB_PASSWORD=secure_password
```

### 6. Run Database Setup Script

```bash
python scripts/setup_db.py
```

This script:
1. Runs all migrations
2. Creates initial roles (SUPER_ADMIN, USER)
3. Creates initial permissions
4. Assigns permissions to roles
5. Creates superuser account interactively

### 7. Start Development Server

```bash
python manage.py runserver
```

Access:
- Admin panel: http://localhost:8000/admin/
- API (future): http://localhost:8000/api/

## Admin Panel

### Features

- **User Management**: Create, edit, soft-delete users
- **Role Management**: Define roles with descriptions
- **Permission Management**: Create fine-grained permissions
- **Assignment**: Assign roles to users and permissions to roles
- **Audit Trail**: View who created/modified/deleted records
- **Status Badges**: Visual indicators for active/inactive status

### Customizations

- **User Admin**:
  - Display: username, email, active status, staff status, creation date
  - Search: by username and email
  - Filters: by active status, staff status, creation date
  - Collapsible audit section

- **Role Admin**:
  - Display: name, description, permission count, creation date
  - Inline: Add/remove permissions directly
  - Filters: by creation date

- **Permission Admin**:
  - Display: code, description, assigned role count, creation date
  - Filters: by creation date
  - Search: by code and description

## API Endpoints (Future - Sprint 2)

Currently, this service focuses on Django admin and core models.

Future endpoints will include:
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration
- `GET /api/users/` - List users
- `POST /api/users/` - Create user
- `GET /api/roles/` - List roles
- `POST /api/permissions/` - Assign permission

## Management Commands

### Migrations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations
```

### Management

```bash
# Create superuser
python manage.py createsuperuser

# Create shell
python manage.py shell

# Collect static files
python manage.py collectstatic

# Check project setup
python manage.py check
```

## Development

### Database Schema

Run migrations to create tables:

```bash
python manage.py migrate
```

Tables created:
- `users` - Custom user model
- `roles` - Role definitions
- `permissions` - Permission definitions
- `user_roles` - User-role assignments
- `role_permissions` - Role-permission assignments
- Django auth tables (for compatibility)

### Querying Examples

```python
from accounts.models import User, Role, Permission, UserRole, RolePermission

# Get active users
users = User.objects.filter(deleted_at__isnull=True)

# Get user roles
user = User.objects.get(username='john')
user_roles = user.user_roles.all()
for ur in user_roles:
    print(f"Role: {ur.role.name}")

# Get role permissions
role = Role.objects.get(name='USER')
permissions = role.role_permissions.all()
for rp in permissions:
    print(f"Permission: {rp.permission.code}")

# Check if user has permission (to implement in utilities)
def has_permission(user, permission_code):
    return user.user_roles.filter(
        role__role_permissions__permission__code=permission_code
    ).exists()
```

### Adding New Users via Admin

1. Go to http://localhost:8000/admin/
2. Click "Users" → "Add User"
3. Fill in username and email
4. Set password using the password field
5. Select active status and staff privileges
6. Click "Save"

### Adding New Roles via Admin

1. Go to http://localhost:8000/admin/
2. Click "Roles" → "Add Role"
3. Enter role name and description
4. Click "Save"
5. Assign permissions using the inline form

## Best Practices

### Audit Trail

Always track who performs operations:

```python
user.created_by = "admin"
user.save()
```

### Soft Delete

Use soft delete for data retention:

```python
# Soft delete
user.soft_delete(deleted_by="admin")

# Query only active records
active = User.objects.filter(deleted_at__isnull=True)

# Include deleted in query
all_records = User.objects.all()  # Use with caution
```

### Permissions

Keep permission codes consistent:
- Format: `resource.action` (e.g., "user.create", "role.delete")
- Granular: One permission per action
- Reusable: Group permissions in roles

### Roles

- **SUPER_ADMIN**: Full system access
- **USER**: Basic read-only access
- Custom roles: Define as needed for future features

## File Documentation

### [authservice/settings.py](authservice/settings.py)
Main Django configuration with PostgreSQL connection, installed apps, middleware, and security settings.

### [accounts/models.py](accounts/models.py)
Database models including:
- `AuditedModel`: Abstract base with audit fields
- `User`: Custom user model with UUID PK
- `Role`, `Permission`: RBAC entities
- `UserRole`, `RolePermission`: Relationship models

### [accounts/admin.py](accounts/admin.py)
Django admin customization with:
- Custom User admin with audit display
- Role and Permission admins
- Relationship admins
- Color-coded status badges
- Inline permission assignment

### [scripts/setup_db.py](scripts/setup_db.py)
Database initialization script that:
1. Runs migrations
2. Creates seed data (initial roles and permissions)
3. Assigns permissions to roles
4. Creates superuser interactively

## Troubleshooting

### PostgreSQL Connection Error

```
Error: could not connect to server
```

**Solution**: Check PostgreSQL is running and credentials in `.env`:
```bash
# Test connection
psql -U postgres -h localhost -d aura_auth_db
```

### Migration Conflicts

```
Error: Conflicting migrations detected
```

**Solution**: Delete migration files except `__init__.py` in `accounts/migrations/` and rerun:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Admin Panel Not Loading

```
Error: 404 - Page not found
```

**Solution**: Ensure migrations are applied:
```bash
python manage.py migrate
```

## Next Steps (Future Sprints)

- **Sprint 2**: REST API endpoints (Django REST Framework)
- **Sprint 3**: JWT authentication and token management
- **Sprint 4**: Integration with other microservices
- **Sprint 5**: Advanced features (2FA, password recovery, etc.)

## License

Internal project for Aura System

## Support

For issues or questions, contact the backend team.
