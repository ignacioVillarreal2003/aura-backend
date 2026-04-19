"""
Initial database setup script.

This script:
1. Creates the database (if using PostgreSQL)
2. Runs migrations
3. Creates seed data (initial roles)
4. Creates superuser
"""

import os
import sys
import django
from pathlib import Path

# Setup Django - point to project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'authservice.settings')
django.setup()

from django.db import connection
from django.core.management import execute_from_command_line
from accounts.models import Role, Permission, User, PermissionInRole, UserRole


def create_initial_roles():
    """Create initial roles for the system."""
    roles_data = [
        {
            'name': 'superadmin',
            'description': 'Super administrator with all permissions'
        },
        {
            'name': 'user',
            'description': 'Regular user with basic permissions'
        },
        {
            'name': 'admin',
            'description': 'Administrator role'
        },
    ]
    
    for role_data in roles_data:
        role, created = Role.objects.get_or_create(
            name=role_data['name'],
            defaults={'description': role_data['description']}
        )
        if created:
            print(f"✓ Created role: {role.name}")
        else:
            print(f"• Role already exists: {role.name}")


def create_initial_permissions():
    """Create initial permissions for the system."""
    permissions_data = [
        # User permissions
        {'name': 'user.create', 'description': 'Create new users'},
        {'name': 'user.read', 'description': 'View user details'},
        {'name': 'user.update', 'description': 'Update user information'},
        {'name': 'user.delete', 'description': 'Delete users'},
        {'name': 'user.list', 'description': 'List all users'},

        # Role permissions
        {'name': 'role.create', 'description': 'Create new roles'},
        {'name': 'role.read', 'description': 'View role details'},
        {'name': 'role.update', 'description': 'Update roles'},
        {'name': 'role.delete', 'description': 'Delete roles'},
        {'name': 'role.list', 'description': 'List all roles'},

        # Permission permissions
        {'name': 'permission.create', 'description': 'Create new permissions'},
        {'name': 'permission.read', 'description': 'View permission details'},
        {'name': 'permission.update', 'description': 'Update permissions'},
        {'name': 'permission.delete', 'description': 'Delete permissions'},
        {'name': 'permission.list', 'description': 'List all permissions'},
    ]
    
    for perm_data in permissions_data:
        perm, created = Permission.objects.get_or_create(
            name=perm_data['name'],
            defaults={'description': perm_data['description']}
        )
        if created:
            print(f"✓ Created permission: {perm.name}")
        else:
            print(f"• Permission already exists: {perm.name}")


def normalize_existing_rbac_names():
    """Normalize existing role/permission records to lowercase naming."""
    for role in Role.objects.all():
        normalized_name = (role.name or '').lower()
        if normalized_name and role.name != normalized_name:
            role.name = normalized_name
            role.save(update_fields=['name'])

    for permission in Permission.objects.all():
        normalized_name = (permission.name or '').lower()
        if normalized_name and permission.name != normalized_name:
            permission.name = normalized_name
            permission.save(update_fields=['name'])


def assign_permissions_to_roles():
    """Assign permissions to initial roles."""
    try:
        super_admin = Role.objects.get(name='superadmin')
        user_role = Role.objects.get(name='user')
        
        # superadmin gets all permissions
        all_permissions = Permission.objects.all()
        for perm in all_permissions:
            PermissionInRole.objects.get_or_create(role=super_admin, permission=perm)
        print(f"✓ Assigned {all_permissions.count()} permissions to superadmin")
        
        # user gets only read permissions
        read_permissions = Permission.objects.filter(name__contains='read')
        for perm in read_permissions:
            PermissionInRole.objects.get_or_create(role=user_role, permission=perm)
        print(f"✓ Assigned {read_permissions.count()} read permissions to user")
        
    except Role.DoesNotExist:
        print("✗ Roles not found. Please create them first.")


def main():
    """Main setup function."""
    print("\n" + "="*60)
    print("Aura Authentication Service - Initial Setup")
    print("="*60 + "\n")
    
    # Step 1: Create migrations
    print("Step 1: Creating migrations...")
    try:
        execute_from_command_line(['manage.py', 'makemigrations', 'accounts'])
        print("✓ Migrations created\n")
    except Exception as e:
        print(f"✗ Migration creation failed: {e}\n")
        return
    
    # Step 2: Run migrations
    print("Step 2: Running migrations...")
    try:
        execute_from_command_line(['manage.py', 'migrate'])
        print("✓ Migrations completed\n")
    except Exception as e:
        print(f"✗ Migration failed: {e}\n")
        return
    
    # Step 3: Create initial roles
    print("Step 3: Creating initial roles...")
    try:
        normalize_existing_rbac_names()
        create_initial_roles()
        print()
    except Exception as e:
        print(f"✗ Role creation failed: {e}\n")
        return
    
    # Step 3: Create initial permissions
    print("Step 3: Creating initial permissions...")
    try:
        create_initial_permissions()
        print()
    except Exception as e:
        print(f"✗ Permission creation failed: {e}\n")
        return
    
    # Step 4: Assign permissions to roles
    print("Step 4: Assigning permissions to roles...")
    try:
        assign_permissions_to_roles()
        print()
    except Exception as e:
        print(f"✗ Permission assignment failed: {e}\n")
        return
    
    # Step 5: Create superuser
    print("Step 5: Create superuser account")
    print("-" * 40)
    try:
        username = input("Enter superuser username (default: admin): ").strip() or "admin"
        email = input("Enter superuser email: ").strip()
        
        if not email:
            print("✗ Email is required")
            return
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            print(f"✗ User '{username}' already exists")
            return
        
        password = input("Enter superuser password: ").strip()
        if not password:
            print("✗ Password is required")
            return
        
        superuser = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        super_admin_role = Role.objects.get(name='superadmin')
        UserRole.objects.get_or_create(
            user=superuser,
            role=super_admin_role,
            defaults={'created_by': superuser},
        )
        
        print(f"✓ Superuser '{username}' created successfully")
        print(f"  Email: {email}")
        print(f"  Role: superadmin\n")
        
    except Exception as e:
        print(f"✗ Superuser creation failed: {e}\n")
        return
    
    # Summary
    print("="*60)
    print("Setup completed successfully!")
    print("="*60)
    print("\nNext steps:")
    print("1. Start the development server:")
    print("   python manage.py runserver")
    print("\n2. Access the admin panel:")
    print("   http://localhost:8000/admin/")
    print(f"\n3. Login with username: {username}")
    print("\n" + "="*60 + "\n")


if __name__ == '__main__':
    main()
