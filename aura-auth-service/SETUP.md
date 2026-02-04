# Database Setup Instructions

Complete step-by-step guide for setting up the Aura Authentication Service database.

## Prerequisites

- PostgreSQL 17 installed and running
- Python 3.13+ with virtual environment activated
- Django dependencies installed (`pip install -r requirements.txt`)

## Quick Start (Automated)

```bash
# Windows
python scripts/setup_db.py

# Linux/macOS
python scripts/setup_db.py
```

This single script will:
1. Create all database tables (migrations)
2. Create initial roles (SUPER_ADMIN, USER)
3. Create initial permissions
4. Assign permissions to roles
5. Prompt you to create a superuser

## Manual Setup (Step-by-Step)

### Step 1: Create PostgreSQL Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE aura_auth_db;

# Create user
CREATE USER aura_user WITH PASSWORD 'secure_password_here';

# Configure user
ALTER ROLE aura_user SET client_encoding TO 'utf8';
ALTER ROLE aura_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE aura_user SET default_transaction_deferrable TO on;
ALTER ROLE aura_user SET timezone TO 'UTC';

# Grant permissions
GRANT ALL PRIVILEGES ON DATABASE aura_auth_db TO aura_user;

# Exit
\q
```

### Step 2: Update .env File

```env
DEBUG=True
SECRET_KEY=your-very-long-secret-key-change-in-production

DB_ENGINE=django.db.backends.postgresql
DB_NAME=aura_auth_db
DB_USER=aura_user
DB_PASSWORD=secure_password_here
DB_HOST=localhost
DB_PORT=5432
```

### Step 3: Create Migrations

```bash
python manage.py makemigrations accounts
```

**Output:**
```
Migrations for 'accounts':
  accounts/migrations/0001_initial.py
    - Create model AuditedModel
    - Create model User
    - Create model Role
    - Create model Permission
    - Create model UserRole
    - Create model RolePermission
```

### Step 4: Apply Migrations

```bash
python manage.py migrate
```

**Output:**
```
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, sessions, accounts
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  ...
  Applying accounts.0001_initial... OK
```

**Database tables created:**
- `users` - Custom user model
- `roles` - Role definitions
- `permissions` - Permission definitions
- `user_roles` - User-role assignments
- `role_permissions` - Role-permission assignments

### Step 5: Create Initial Roles

```bash
python manage.py shell
```

Then in the Django shell:

```python
from accounts.models import Role

# Create SUPER_ADMIN role
super_admin, created = Role.objects.get_or_create(
    name='SUPER_ADMIN',
    defaults={'description': 'Super administrator with all permissions'}
)
print(f"SUPER_ADMIN: {'Created' if created else 'Already exists'}")

# Create USER role
user_role, created = Role.objects.get_or_create(
    name='USER',
    defaults={'description': 'Regular user with basic permissions'}
)
print(f"USER: {'Created' if created else 'Already exists'}")

exit()
```

### Step 6: Create Initial Permissions

```bash
python manage.py shell
```

Then:

```python
from accounts.models import Permission

permissions = [
    ('user.create', 'Create new users'),
    ('user.read', 'View user details'),
    ('user.update', 'Update user information'),
    ('user.delete', 'Delete users'),
    ('user.list', 'List all users'),
    ('role.create', 'Create new roles'),
    ('role.read', 'View role details'),
    ('role.update', 'Update roles'),
    ('role.delete', 'Delete roles'),
    ('role.list', 'List all roles'),
    ('permission.create', 'Create new permissions'),
    ('permission.read', 'View permission details'),
    ('permission.update', 'Update permissions'),
    ('permission.delete', 'Delete permissions'),
    ('permission.list', 'List all permissions'),
]

for code, description in permissions:
    perm, created = Permission.objects.get_or_create(
        code=code,
        defaults={'description': description}
    )
    print(f"{code}: {'Created' if created else 'Already exists'}")

exit()
```

### Step 7: Assign Permissions to Roles

```bash
python manage.py shell
```

Then:

```python
from accounts.models import Role, Permission

# Get roles
super_admin = Role.objects.get(name='SUPER_ADMIN')
user_role = Role.objects.get(name='USER')

# SUPER_ADMIN gets all permissions
all_perms = Permission.objects.filter(deleted_at__isnull=True)
for perm in all_perms:
    super_admin.role_permissions.get_or_create(permission=perm)
print(f"✓ Assigned {all_perms.count()} permissions to SUPER_ADMIN")

# USER gets only read permissions
read_perms = Permission.objects.filter(code__endswith='read')
for perm in read_perms:
    user_role.role_permissions.get_or_create(permission=perm)
print(f"✓ Assigned {read_perms.count()} read permissions to USER")

exit()
```

### Step 8: Create Superuser

```bash
python manage.py createsuperuser
```

**Prompt:**
```
Username: admin
Email: admin@example.com
Password: 
Password (again):
```

## Verification

### Check Database Connection

```bash
python manage.py dbshell
```

Should open a PostgreSQL prompt. Type `\dt` to see tables:

```sql
\dt

              List of relations
 Schema |     Name      | Type  |  Owner
--------+---------------+-------+----------
 public | accounts_permission | table | aura_user
 public | accounts_role | table | aura_user
 public | accounts_rolepermission | table | aura_user
 public | accounts_user | table | aura_user
 public | accounts_userrole | table | aura_user
 ...
```

### Check Django Setup

```bash
python manage.py check
```

Should output:
```
System check identified no issues (0 silenced).
```

### Test Admin Login

```bash
python manage.py runserver
```

Visit: http://localhost:8000/admin/

Login with superuser credentials.

## Troubleshooting

### "psycopg2.OperationalError: could not connect to server"

**Cause**: PostgreSQL not running or wrong credentials

**Solution**:
1. Verify PostgreSQL is running:
   ```bash
   # Windows
   pg_isready -h localhost -p 5432
   
   # Linux/macOS
   psql -h localhost -U postgres -c "SELECT 1"
   ```

2. Check `.env` credentials match actual database

3. Verify database exists:
   ```bash
   psql -U postgres -l | grep aura_auth_db
   ```

### "FATAL: Ident authentication failed for user"

**Cause**: PostgreSQL authentication issue

**Solution**: Update `pg_hba.conf` to use md5 authentication:
```
# Change this line in pg_hba.conf:
# FROM: host    all             all             127.0.0.1/32            ident
# TO:   host    all             all             127.0.0.1/32            md5
```

Then restart PostgreSQL and try again.

### "No migrations detected in app 'accounts'"

**Cause**: Migrations folder not initialized

**Solution**:
```bash
# Ensure migrations folder exists
mkdir -p accounts/migrations
touch accounts/migrations/__init__.py

# Create migrations
python manage.py makemigrations accounts
```

### Migration Conflicts

**Cause**: Multiple migration files with same state

**Solution**:
```bash
# Backup existing migrations (just in case)
mv accounts/migrations accounts/migrations.backup

# Recreate migrations folder
mkdir -p accounts/migrations
touch accounts/migrations/__init__.py

# Create fresh migrations
python manage.py makemigrations accounts

# Apply
python manage.py migrate
```

### Admin Page Returns 404

**Cause**: Tables not created (migrations not applied)

**Solution**:
```bash
python manage.py migrate
python manage.py runserver
```

## Database Schema Overview

### Users Table
```sql
SELECT * FROM users WHERE deleted_at IS NULL;
```

### Roles Table
```sql
SELECT * FROM roles WHERE deleted_at IS NULL;
```

### User Roles Assignment
```sql
SELECT u.username, r.name 
FROM user_roles ur
JOIN users u ON ur.user_id = u.id
JOIN roles r ON ur.role_id = r.id;
```

### Role Permissions Assignment
```sql
SELECT r.name, p.code 
FROM role_permissions rp
JOIN roles r ON rp.role_id = r.id
JOIN permissions p ON rp.permission_id = p.id;
```

## Backup and Restore

### Backup Database

```bash
# Dump database
pg_dump -U aura_user aura_auth_db > backup.sql

# Dump with data
pg_dump -U aura_user --data-only aura_auth_db > data_backup.sql
```

### Restore Database

```bash
# Drop old database
psql -U postgres -c "DROP DATABASE aura_auth_db;"

# Restore
psql -U postgres -f backup.sql
```

## Clean Database (Development Only)

**WARNING: This deletes all data!**

```bash
# Method 1: Flush all data (keep migrations)
python manage.py flush

# Method 2: Reset migrations
python manage.py migrate accounts zero

# Method 3: Complete reset
python manage.py migrate accounts zero
python manage.py makemigrations accounts --empty --name reset_migrations
python manage.py migrate
```

## Next Steps

1. ✅ Database setup complete
2. 📝 Create Django admin users
3. 🔐 Assign roles and permissions
4. 🚀 Start development server
5. 📚 Build API endpoints (Sprint 2)
