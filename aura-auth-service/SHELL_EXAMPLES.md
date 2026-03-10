# Django Shell Examples

This document shows common operations using the Django shell.

## Opening the Shell

```bash
python manage.py shell
```

Or with IPython (better experience):

```bash
pip install ipython
python manage.py shell
```

## User Operations

### Create a User

```python
from accounts.models import User

# Create a regular user
user = User.objects.create_user(
    username='john',
    email='john@example.com',
    password='secure_password_123'
)
print(user)  # john (john@example.com)
```

### List All Users

```python
from accounts.models import User

# Get all active users
users = User.objects.filter(deleted_at__isnull=True)
for user in users:
    print(f"{user.username} - {user.email}")
```

### Update a User

```python
user = User.objects.get(username='john')
user.email = 'john.doe@example.com'
user.save()
print(f"Updated: {user.email}")
```

### Soft Delete a User

```python
user = User.objects.get(username='john')
user.soft_delete(deleted_by='admin')
print(f"User deleted at: {user.deleted_at}")

# Verify user is hidden from queries
User.objects.filter(deleted_at__isnull=True).count()  # John won't be here
```

### Restore a Deleted User

```python
user = User.objects.get(username='john')
user.restore()
print(f"User restored. Deleted at: {user.deleted_at}")
```

### Check User Passwords

```python
user = User.objects.get(username='john')

# Check password
if user.check_password('secure_password_123'):
    print("Password is correct")

# Set new password
user.set_password('new_password')
user.save()
print("Password updated")
```

### Get User Roles

```python
from accounts.models import User

user = User.objects.get(username='john')

# Get all roles assigned to this user
roles = user.user_roles.all()
for user_role in roles:
    print(f"Role: {user_role.role.name}")
```

### Get User Permissions

```python
from accounts.utils import get_user_permissions

user = User.objects.get(username='john')
permissions = get_user_permissions(user)
for perm in permissions:
    print(f"Permission: {perm}")
```

## Role Operations

### Create a Role

```python
from accounts.models import Role

role = Role.objects.create(
    name='MANAGER',
    description='Manager with enhanced permissions'
)
print(f"Created: {role.name}")
```

### List All Roles

```python
from accounts.models import Role

roles = Role.objects.filter(deleted_at__isnull=True)
for role in roles:
    print(f"{role.name}: {role.description}")
```

### Get Role Permissions

```python
from accounts.models import Role

role = Role.objects.get(name='SUPER_ADMIN')
permissions = role.role_permissions.all()
print(f"Role '{role.name}' has {permissions.count()} permissions:")
for rp in permissions:
    print(f"  - {rp.permission.code}")
```

### Assign Role to User

```python
from accounts.models import User, Role
from accounts.utils import assign_role_to_user

user = User.objects.get(username='john')
role = Role.objects.get(name='MANAGER')

# Assign role
user_role = assign_role_to_user(
    user=user,
    role=role,
    assigned_by='admin'
)
print(f"Assigned {role.name} to {user.username}")
```

### Remove Role from User

```python
from accounts.models import User, Role

user = User.objects.get(username='john')
role = Role.objects.get(name='MANAGER')

# Remove role
user.user_roles.filter(role=role).delete()
print(f"Removed {role.name} from {user.username}")
```

## Permission Operations

### Create a Permission

```python
from accounts.models import Permission

perm = Permission.objects.create(
    code='report.export',
    description='Export reports to PDF or Excel'
)
print(f"Created: {perm.code}")
```

### List All Permissions

```python
from accounts.models import Permission

perms = Permission.objects.filter(deleted_at__isnull=True)
for perm in perms:
    print(f"{perm.code}: {perm.description}")
```

### Assign Permission to Role

```python
from accounts.models import Role, Permission
from accounts.utils import assign_permission_to_role

role = Role.objects.get(name='MANAGER')
perm = Permission.objects.get(code='report.export')

# Assign permission
role_perm = assign_permission_to_role(
    role=role,
    permission=perm,
    granted_by='admin'
)
print(f"Assigned {perm.code} to {role.name}")
```

### Check User Permission

```python
from accounts.utils import user_has_permission

user = User.objects.get(username='john')

# Check if user has permission
has_perm = user_has_permission(user, 'report.export')
print(f"User has 'report.export': {has_perm}")
```

### Check User Role

```python
from accounts.utils import user_has_role

user = User.objects.get(username='john')

# Check if user has role
has_role = user_has_role(user, 'MANAGER')
print(f"User has MANAGER role: {has_role}")
```

## Advanced Queries

### Get Users with Specific Role

```python
from accounts.models import User, Role

role = Role.objects.get(name='MANAGER')
users = User.objects.filter(
    user_roles__role=role,
    deleted_at__isnull=True
).distinct()

for user in users:
    print(user.username)
```

### Get Roles with Specific Permission

```python
from accounts.models import Role, Permission

perm = Permission.objects.get(code='user.create')
roles = Role.objects.filter(
    role_permissions__permission=perm,
    deleted_at__isnull=True
).distinct()

for role in roles:
    print(role.name)
```

### Get All Users and Their Roles

```python
from accounts.models import User

users = User.objects.prefetch_related('user_roles__role').filter(
    deleted_at__isnull=True
)

for user in users:
    roles = [ur.role.name for ur in user.user_roles.all()]
    print(f"{user.username}: {', '.join(roles) or 'No roles'}")
```

### Count Users per Role

```python
from django.db.models import Count
from accounts.models import Role

role_counts = Role.objects.filter(
    deleted_at__isnull=True
).annotate(
    user_count=Count('user_assignments')
).values('name', 'user_count')

for role in role_counts:
    print(f"{role['name']}: {role['user_count']} users")
```

### Count Permissions per Role

```python
from django.db.models import Count
from accounts.models import Role

role_perms = Role.objects.filter(
    deleted_at__isnull=True
).annotate(
    perm_count=Count('role_permissions')
).values('name', 'perm_count')

for role in role_perms:
    print(f"{role['name']}: {role['perm_count']} permissions")
```

## Audit Trail Queries

### Get User's Creation Info

```python
user = User.objects.get(username='admin')
print(f"Created: {user.created_at} by {user.created_by}")
print(f"Updated: {user.updated_at} by {user.updated_by}")
if user.deleted_at:
    print(f"Deleted: {user.deleted_at} by {user.deleted_by}")
```

### Get Recently Created Users

```python
from django.utils import timezone
from datetime import timedelta

last_24h = timezone.now() - timedelta(hours=24)
recent = User.objects.filter(
    created_at__gte=last_24h,
    deleted_at__isnull=True
)

for user in recent:
    print(f"{user.username} - Created by {user.created_by}")
```

### Get Deleted Users

```python
deleted = User.objects.filter(deleted_at__isnull=False)
for user in deleted:
    print(f"{user.username} - Deleted by {user.deleted_by}")
```

## Bulk Operations

### Assign Role to Multiple Users

```python
from accounts.models import User, Role

users = User.objects.filter(username__startswith='user_')
role = Role.objects.get(name='USER')

for user in users:
    user.user_roles.get_or_create(role=role, defaults={'assigned_by': 'admin'})
    print(f"Assigned {role.name} to {user.username}")
```

### Remove Permission from Role

```python
from accounts.models import Role, Permission

role = Role.objects.get(name='USER')
perm = Permission.objects.get(code='user.delete')

role.role_permissions.filter(permission=perm).delete()
print(f"Removed {perm.code} from {role.name}")
```

### Bulk Soft Delete

```python
from accounts.models import User
from django.utils import timezone

# Soft delete all inactive users (be careful!)
inactive = User.objects.filter(is_active=False)
for user in inactive:
    user.soft_delete(deleted_by='system')
    print(f"Deleted: {user.username}")
```

## Useful Django ORM Commands

### Get or Create

```python
from accounts.models import User

user, created = User.objects.get_or_create(
    username='jane',
    defaults={
        'email': 'jane@example.com',
        'is_active': True
    }
)
print(f"User: {'Created' if created else 'Already exists'}")
```

### Update Multiple Records

```python
from accounts.models import User

# Deactivate all users created in the last 7 days
from django.utils import timezone
from datetime import timedelta

week_ago = timezone.now() - timedelta(days=7)
User.objects.filter(created_at__gte=week_ago).update(is_active=False)
```

### Delete Query Results (without soft delete)

```python
# WARNING: This does HARD delete, not soft delete!
from accounts.models import User

# Wrong way (hard delete):
User.objects.filter(username='test').delete()

# Right way (soft delete):
for user in User.objects.filter(username='test'):
    user.soft_delete(deleted_by='admin')
```

### Exit Shell

```python
exit()
# or
quit()
```

## Tips

1. **Use `print()` liberally** to see query results
2. **Use `.query` to see SQL**: `User.objects.all().query`
3. **Use `dir(object)` to explore**: `dir(user)`
4. **Use `help(Model)` for docs**: `help(User)`
5. **Reload modules**: `import importlib; importlib.reload(accounts.models)`
6. **Create test data easily**: Use the functions above
7. **Check migrations**: `python manage.py showmigrations accounts`

