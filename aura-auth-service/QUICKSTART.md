# Quick Start Guide

Get the Aura Auth Service running in 5 minutes.

## 1. Install Dependencies (1 min)

```bash
pip install -r requirements.txt
```

## 2. Configure Database (1 min)

Edit `.env`:
```env
DB_NAME=aura_auth_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
```

Create database (if not exists):
```bash
createdb aura_auth_db
```

## 3. Run Setup Script (2 min)

```bash
python scripts/setup_db.py
```

**What it does:**
- ✅ Creates all tables (migrations)
- ✅ Creates initial roles (SUPER_ADMIN, USER)
- ✅ Creates permissions
- ✅ Assigns permissions to roles
- ✅ Creates superuser (interactive)

## 4. Start Development Server (30 sec)

```bash
python manage.py runserver
```

## 5. Access Admin Panel (30 sec)

Open in browser:
```
http://localhost:8000/admin/
```

Login with superuser credentials created in step 3.

---

## Common Commands

```bash
# Create shell (interactive Python with Django)
python manage.py shell

# Check project setup
python manage.py check

# View database
python manage.py dbshell

# Run tests
python manage.py test accounts

# Create migrations (if models changed)
python manage.py makemigrations accounts

# Apply migrations
python manage.py migrate
```

---

## Windows Users

Use `run.bat` for shortcuts:

```bash
run.bat install          # Install dependencies
run.bat migrate          # Apply migrations
run.bat setup            # Run setup script
run.bat runserver        # Start server
run.bat shell            # Open Django shell
```

## Linux/macOS Users

Use `run.sh`:

```bash
./run.sh install
./run.sh migrate
./run.sh setup
./run.sh runserver
./run.sh shell
```

---

## What's Included

✅ Custom User model with soft delete
✅ Role-Based Access Control (RBAC)
✅ Permission management
✅ Audit trail (created_at, created_by, updated_at, updated_by, deleted_at, deleted_by)
✅ PostgreSQL database
✅ Django admin panel customization
✅ Unit tests
✅ Helper utilities

---

## Admin Features

- Create/manage users
- Create/manage roles
- Create/manage permissions
- Assign roles to users
- Assign permissions to roles
- View complete audit trail
- Soft delete records
- Search and filter

---

## Next Steps

1. Read [README.md](README.md) for detailed documentation
2. Check [SETUP.md](SETUP.md) for in-depth setup guide
3. Explore [SHELL_EXAMPLES.md](SHELL_EXAMPLES.md) for Django shell usage
4. Review [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for architecture details

---

## Troubleshooting

### Error: "could not connect to server"
PostgreSQL not running. Start it:
```bash
# Windows: Services > PostgreSQL > Start
# macOS: brew services start postgresql
# Linux: sudo systemctl start postgresql
```

### Error: "database does not exist"
Create it:
```bash
createdb aura_auth_db
```

### Admin page shows 404
Run migrations:
```bash
python manage.py migrate
```

### Need to reset database
```bash
python manage.py migrate accounts zero
python manage.py migrate
python scripts/setup_db.py
```

---

## Production Deployment

For production, refer to:
- [README.md](README.md) - Security settings section
- [SETUP.md](SETUP.md) - Backup and restore section
- [settings.py](authservice/settings.py) - Security configuration

**Key steps:**
1. Set `DEBUG=False` in .env
2. Use strong `SECRET_KEY`
3. Configure `ALLOWED_HOSTS`
4. Set up proper PostgreSQL user with limited permissions
5. Use environment-specific .env file
6. Run on WSGI server (Gunicorn)
7. Use SSL/HTTPS
8. Set up logging and monitoring

---

## Support

Questions? Check:
- 📖 [README.md](README.md) - Full documentation
- 🔧 [SETUP.md](SETUP.md) - Setup troubleshooting
- 💻 [SHELL_EXAMPLES.md](SHELL_EXAMPLES.md) - Django shell usage
- 📋 [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Architecture overview

---

Ready to go! 🚀
