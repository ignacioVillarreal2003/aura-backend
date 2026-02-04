# File Structure & Documentation

Complete guide to every file in the Aura Authentication Service.

## Project Root Files

### [manage.py](manage.py)
**Type**: Python script (executable)

**Purpose**: Django management command runner

**Usage**:
```bash
python manage.py migrate          # Run migrations
python manage.py runserver        # Start dev server
python manage.py shell            # Open interactive shell
python manage.py test accounts    # Run tests
```

**Content**: Standard Django manage.py (no modifications)

---

### [requirements.txt](requirements.txt)
**Type**: Configuration file

**Purpose**: Python dependencies list

**Key packages**:
- `Django==5.1.6` - Web framework
- `psycopg2-binary==2.9.11` - PostgreSQL adapter
- `python-decouple==3.8` - Environment variables
- `djangorestframework==3.14.0` - REST API (future)
- `django-cors-headers==4.3.1` - CORS support
- `gunicorn==23.0.0` - Production server

**Install**:
```bash
pip install -r requirements.txt
```

---

### [.env](.env)
**Type**: Configuration file (DO NOT COMMIT)

**Purpose**: Environment variables for local development

**Structure**:
```env
# Django
DEBUG=True
SECRET_KEY=django-insecure-change-in-production

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=aura_auth_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Environment
ENVIRONMENT=development
```

**⚠️ Security**: Never commit to Git. Change SECRET_KEY in production.

---

### [.gitignore](.gitignore)
**Type**: Git configuration

**Purpose**: Specify files/folders to exclude from version control

**Excludes**:
- `__pycache__/` - Python cache
- `*.pyc` - Compiled Python
- `venv/`, `env/` - Virtual environments
- `db.sqlite3` - Database files
- `.env` - Credentials
- `staticfiles/`, `media/` - User uploads
- `.vscode/`, `.idea/` - IDE settings
- Logs and temporary files

---

### [README.md](README.md)
**Type**: Documentation (Markdown)

**Length**: Comprehensive (1000+ lines)

**Purpose**: Main project documentation

**Sections**:
- Project overview
- Architecture details
- Technology stack
- Database models reference
- Features explanation
- Setup instructions (quick and detailed)
- Admin panel guide
- API endpoints (future)
- Management commands
- Development guide
- Troubleshooting
- Next steps
- Support

**Audience**: Developers, system administrators, project managers

---

### [QUICKSTART.md](QUICKSTART.md)
**Type**: Documentation (Markdown)

**Length**: Short (200 lines)

**Purpose**: Get started in 5 minutes

**Sections**:
- 5-step quick start
- Common commands
- Windows/Linux usage
- What's included
- Admin features
- Troubleshooting
- Production notes

**Audience**: Developers who want to start immediately

---

### [SETUP.md](SETUP.md)
**Type**: Documentation (Markdown)

**Length**: Long (400+ lines)

**Purpose**: Detailed database setup guide

**Sections**:
- Prerequisites
- Quick start (automated)
- Manual setup (step-by-step)
- Verification procedures
- Troubleshooting with solutions
- Backup and restore procedures
- Database schema queries
- Clean database procedures

**Audience**: DevOps, database administrators, troubleshooters

---

### [SHELL_EXAMPLES.md](SHELL_EXAMPLES.md)
**Type**: Documentation (Markdown)

**Length**: Long (600+ lines)

**Purpose**: Django shell usage examples

**Sections**:
- Opening the shell
- User operations (CRUD, password, soft delete)
- Role operations
- Permission operations
- User role assignments
- Permission assignments
- Advanced queries
- Audit trail queries
- Bulk operations
- Tips and tricks

**Audience**: Developers, database administrators

---

### [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
**Type**: Documentation (Markdown)

**Length**: Very long (700+ lines)

**Purpose**: Complete project summary and architecture guide

**Sections**:
- Project overview
- Deliverables checklist
- Technology stack
- Database models (detailed)
- Key features
- File documentation
- Setup instructions
- Initial data
- Best practices
- Testing
- Admin features
- Database queries
- Next steps
- Troubleshooting
- File checklist
- Performance considerations
- Security checklist

**Audience**: Architects, senior developers, project leads

---

### [run.bat](run.bat)
**Type**: Windows batch script

**Purpose**: Convenient command shortcuts for Windows users

**Commands**:
```bash
run.bat help              # Show help
run.bat install           # Install dependencies
run.bat makemigrations    # Create migrations
run.bat migrate           # Apply migrations
run.bat setup             # Full setup
run.bat shell             # Django shell
run.bat runserver         # Start server
run.bat createsuperuser   # Create superuser
run.bat check             # Check setup
run.bat clean             # Clean cache
```

**Usage**: 
```bash
run.bat install
run.bat runserver
```

---

### [run.sh](run.sh)
**Type**: Linux/macOS shell script (executable)

**Purpose**: Convenient command shortcuts for Unix users

**Commands**: Same as run.bat

**Usage**:
```bash
chmod +x run.sh
./run.sh install
./run.sh runserver
```

---

## Django Project Directory: authservice/

### [authservice/__init__.py](authservice/__init__.py)
**Type**: Python module marker

**Purpose**: Mark authservice as a Python package

**Content**: Empty (no modifications)

---

### [authservice/settings.py](authservice/settings.py)
**Type**: Python configuration

**Length**: 300+ lines

**Purpose**: Django project configuration

**Key sections**:
1. **Project paths**: BASE_DIR, file locations
2. **Security**: DEBUG, SECRET_KEY, ALLOWED_HOSTS
3. **Apps**: Installed applications (Django built-ins + custom apps)
4. **Middleware**: Request/response processing
5. **Templates**: Template engine configuration
6. **Database**: PostgreSQL connection (environment-based)
7. **Password validators**: Password strength rules
8. **Internationalization**: Language, timezone
9. **Static/media**: File serving
10. **Custom User Model**: AUTH_USER_MODEL = 'accounts.User'
11. **CORS**: Frontend communication
12. **REST Framework**: API configuration
13. **Logging**: Debug and error logging
14. **Security (production)**: SSL, secure cookies

**Key environment variables used**:
- DEBUG, SECRET_KEY, ALLOWED_HOSTS
- DB_* (database connection)
- CORS_ALLOWED_ORIGINS
- ENVIRONMENT

---

### [authservice/urls.py](authservice/urls.py)
**Type**: Python configuration

**Purpose**: Main URL routing

**Routes**:
- `/admin/` - Django admin panel
- `/static/` - Static files (CSS, JS, images)
- `/media/` - User uploads

**Future additions**:
- `/api/` - REST API endpoints (Sprint 2)

**Pattern**: path('route', view_function)

---

### [authservice/wsgi.py](authservice/wsgi.py)
**Type**: Python application

**Purpose**: WSGI application for production servers (Gunicorn)

**Usage**: `gunicorn authservice.wsgi:application`

**Content**: Standard Django WSGI (no modifications)

---

### [authservice/asgi.py](authservice/asgi.py)
**Type**: Python application

**Purpose**: ASGI application for async support (Uvicorn)

**Usage**: `uvicorn authservice.asgi:application`

**Content**: Standard Django ASGI (no modifications)

---

## Accounts App Directory: accounts/

### [accounts/__init__.py](accounts/__init__.py)
**Type**: Python module marker

**Purpose**: Mark accounts as a Python package

**Content**: Empty (no modifications)

---

### [accounts/apps.py](accounts/apps.py)
**Type**: Python configuration

**Length**: 20 lines

**Purpose**: App configuration and metadata

**Key attributes**:
- `name = 'accounts'` - App name
- `default_auto_field` - UUID primary key default
- `verbose_name` - Human-readable name

**Content**:
```python
class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Cuentas y RBAC'
```

---

### [accounts/models.py](accounts/models.py)
**Type**: Python models

**Length**: 500+ lines

**Purpose**: Database models and model logic

**Classes**:
1. **AuditedModel** (abstract)
   - Base class with audit fields
   - Methods: soft_delete(), restore()
   - Properties: is_deleted

2. **CustomUserManager**
   - Manager for User model
   - Methods: create_user(), create_superuser()

3. **User**
   - Custom user model (replaces Django default)
   - Fields: id, username, email, password_hash, is_active, is_staff, is_superuser
   - Audit fields
   - Methods: set_password(), check_password()
   - Indexes and constraints

4. **Role**
   - Role definition
   - Fields: id, name, description
   - Audit fields
   - Indexes and constraints

5. **Permission**
   - Permission definition
   - Fields: id, code, description
   - Audit fields
   - Indexes and constraints

6. **UserRole**
   - User-role relationship
   - Fields: id, user, role, assigned_at, assigned_by

7. **RolePermission**
   - Role-permission relationship
   - Fields: id, role, permission, granted_at, granted_by

**Features**:
- UUID primary keys everywhere
- Soft delete with is_deleted property
- Database indexes and constraints
- Complete docstrings
- Meta classes with db_table, verbose_name, constraints

---

### [accounts/admin.py](accounts/admin.py)
**Type**: Python admin customization

**Length**: 400+ lines

**Purpose**: Django admin panel customization

**Classes**:
1. **UserAdmin**
   - Custom admin for User model
   - List display: username, email, status badges, creation date
   - Filters: active status, staff status, creation date
   - Search: username, email
   - Fieldsets: organized sections
   - Readonly fields: audit fields

2. **RoleAdmin**
   - Custom admin for Role model
   - Display: name, description, permission count badge
   - Filters: creation date
   - Search: name, description

3. **PermissionAdmin**
   - Custom admin for Permission model
   - Display: code, description, role count badge
   - Filters: creation date
   - Search: code, description

4. **UserRoleAdmin**
   - Relationship admin
   - Display: user, role, assignment date and user

5. **RolePermissionAdmin**
   - Relationship admin
   - Display: role, permission, grant date and user

**Features**:
- Color-coded status badges
- Collapsible audit sections
- Inline editing
- Custom display methods
- Readonly fields configuration
- Help text
- Field grouping

---

### [accounts/utils.py](accounts/utils.py)
**Type**: Python utility functions

**Length**: 150+ lines

**Purpose**: Helper functions for RBAC operations

**Functions**:
1. **assign_role_to_user(user, role, assigned_by)**
   - Assign role to user
   - Returns: UserRole instance

2. **assign_permission_to_role(role, permission, granted_by)**
   - Assign permission to role
   - Returns: RolePermission instance

3. **user_has_permission(user, permission_code)**
   - Check if user has specific permission
   - Returns: Boolean
   - Handles superuser bypass

4. **user_has_role(user, role_name)**
   - Check if user has specific role
   - Returns: Boolean
   - Handles superuser bypass

5. **get_user_permissions(user)**
   - Get all user permissions
   - Returns: List of permission codes
   - Handles superuser (returns all)

6. **get_user_roles(user)**
   - Get all user roles
   - Returns: List of role IDs

**Features**:
- Automatic get_or_create to prevent duplicates
- Superuser bypass for permissions
- Respects soft-deleted records
- Comprehensive docstrings

---

### [accounts/tests.py](accounts/tests.py)
**Type**: Python unit tests

**Length**: 350+ lines

**Purpose**: Test all models and utilities

**Test Classes**:
1. **UserModelTest** (11 tests)
   - Creation, uniqueness, soft delete
   - Password hashing and checking
   - Superuser creation
   - Audit fields

2. **RoleModelTest** (4 tests)
   - Creation, uniqueness
   - UUID primary key
   - Soft delete

3. **PermissionModelTest** (2 tests)
   - Creation, uniqueness

4. **UserRoleRelationshipTest** (3 tests)
   - Role assignment
   - Check user has role
   - Unique constraint

5. **RolePermissionRelationshipTest** (2 tests)
   - Permission assignment
   - Unique constraint

6. **UtilityFunctionsTest** (5 tests)
   - user_has_permission()
   - get_user_permissions()
   - get_user_roles()
   - Superuser permissions

**Run tests**:
```bash
python manage.py test accounts
python manage.py test accounts.tests.UserModelTest
python manage.py test accounts.tests.UserModelTest.test_create_user
```

---

### [accounts/views.py](accounts/views.py)
**Type**: Python views (empty, reserved)

**Purpose**: Placeholder for future API views

**Status**: To be implemented in Sprint 2

---

### [accounts/migrations/__init__.py](accounts/migrations/__init__.py)
**Type**: Python module marker

**Purpose**: Mark migrations as a Python package

**Content**: Empty (auto-managed by Django)

---

### [accounts/migrations/0001_initial.py](accounts/migrations/0001_initial.py)
**Type**: Python migration (auto-generated)

**Purpose**: Database schema creation

**Status**: Generated automatically by `python manage.py makemigrations`

**Content**: 
- Create User model
- Create Role model
- Create Permission model
- Create UserRole model
- Create RolePermission model
- Create indexes
- Create constraints

---

## Scripts Directory: scripts/

### [scripts/setup_db.py](scripts/setup_db.py)
**Type**: Python script (executable)

**Length**: 250+ lines

**Purpose**: Automated database initialization

**Main function**: main()

**Steps**:
1. Run migrations
2. Create initial roles (SUPER_ADMIN, USER)
3. Create initial permissions (15 permissions)
4. Assign permissions to roles
5. Create superuser (interactive)

**Usage**:
```bash
python scripts/setup_db.py
```

**Output**: 
- ✓ Progress messages
- Prompts for superuser creation
- Final summary

**Functions**:
- `create_initial_roles()` - Create SUPER_ADMIN and USER roles
- `create_initial_permissions()` - Create user/role/permission permissions
- `assign_permissions_to_roles()` - Assign permissions to initial roles

---

## Directory Structure Summary

```
aura-auth-service/
│
├── 📄 ROOT FILES (Configuration & Documentation)
│   ├── manage.py              [Django management script]
│   ├── requirements.txt       [Python dependencies]
│   ├── .env                   [Environment variables (SECRET)]
│   ├── .gitignore             [Git ignore rules]
│   ├── README.md              [Main documentation]
│   ├── QUICKSTART.md          [5-minute setup]
│   ├── SETUP.md               [Detailed setup guide]
│   ├── SHELL_EXAMPLES.md      [Django shell usage]
│   ├── IMPLEMENTATION_SUMMARY.md [Architecture overview]
│   ├── run.bat                [Windows commands]
│   └── run.sh                 [Unix commands]
│
├── 📁 authservice/ (Django Project)
│   ├── __init__.py
│   ├── settings.py            [Main configuration (300+ lines)]
│   ├── urls.py                [URL routing]
│   ├── wsgi.py                [WSGI application]
│   └── asgi.py                [ASGI application]
│
├── 📁 accounts/ (RBAC Application)
│   ├── __init__.py
│   ├── apps.py                [App configuration]
│   ├── models.py              [All database models (500+ lines)]
│   ├── admin.py               [Admin customization (400+ lines)]
│   ├── utils.py               [Helper functions (150+ lines)]
│   ├── tests.py               [Unit tests (350+ lines)]
│   ├── views.py               [Views (empty, for Sprint 2)]
│   └── migrations/
│       ├── __init__.py
│       └── 0001_initial.py    [Initial schema creation]
│
└── 📁 scripts/ (Utilities)
    └── setup_db.py            [Database initialization (250+ lines)]
```

---

## File Statistics

| Category | Count | Purpose |
|----------|-------|---------|
| **Documentation** | 6 | README, QUICKSTART, SETUP, SHELL_EXAMPLES, IMPLEMENTATION, FILE_STRUCTURE |
| **Configuration** | 4 | manage.py, requirements.txt, .env, .gitignore |
| **Django Project** | 5 | settings.py, urls.py, wsgi.py, asgi.py, __init__.py |
| **Models & Logic** | 5 | models.py, admin.py, utils.py, views.py, apps.py |
| **Tests** | 1 | tests.py (30+ tests) |
| **Database** | 1 | migrations/0001_initial.py |
| **Scripts** | 1 | setup_db.py |
| **Shortcuts** | 2 | run.bat, run.sh |

**Total**: 25+ files, 3000+ lines of code and documentation

---

## How to Navigate

### For Quick Start
→ [QUICKSTART.md](QUICKSTART.md)

### For Setup Help
→ [SETUP.md](SETUP.md)

### For Django Shell Usage
→ [SHELL_EXAMPLES.md](SHELL_EXAMPLES.md)

### For Architecture Details
→ [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

### For Model Details
→ [accounts/models.py](accounts/models.py)

### For Admin Configuration
→ [accounts/admin.py](accounts/admin.py)

### For Database Configuration
→ [authservice/settings.py](authservice/settings.py)

### For Initial Setup
→ [scripts/setup_db.py](scripts/setup_db.py)

---

This completes the file structure documentation.

All files are production-ready and fully documented.
