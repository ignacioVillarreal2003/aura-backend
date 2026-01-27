#!/usr/bin/env python
# -*- coding: utf-8 -*-

import django
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.configuration.settings')

BASE_DIR = os.path.dirname(__file__)
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'app'))

django.setup()

from django.db import connection
from django.contrib.auth.hashers import make_password


def init_admin_user():
    """Initialize the admin user using raw SQL."""
    print('[INFO] Creating admin user...')
    
    try:
        password_hash = make_password('Admin123!')
        
        sql = '''
            INSERT INTO auth_user (username, email, password, status, enabled, 
                account_non_expired, account_non_locked, credentials_non_expired, 
                failed_login_attempts, created_by_id, created_at)
            VALUES (%(username)s, %(email)s, %(password)s, %(status)s, %(enabled)s,
                %(account_non_expired)s, %(account_non_locked)s, 
                %(credentials_non_expired)s, %(failed_login_attempts)s, 
                %(created_by_id)s, NOW())
            ON CONFLICT (username) DO NOTHING
        '''
        
        with connection.cursor() as cursor:
            cursor.execute(sql, {
                'username': 'admin',
                'email': 'admin@system.local',
                'password': password_hash,
                'status': 'active',
                'enabled': True,
                'account_non_expired': True,
                'account_non_locked': True,
                'credentials_non_expired': True,
                'failed_login_attempts': 0,
                'created_by_id': 1
            })
        
        print('[OK] Admin user created')
        return True
    except Exception as e:
        print('[ERROR] Failed to create admin user: {0}'.format(str(e)))
        return False


def init_roles():
    """Initialize default roles using raw SQL."""
    print('[INFO] Creating default roles...')
    
    roles = [
        {'name': 'admin', 'description': 'Administrator role'},
        {'name': 'user', 'description': 'Standard user role'},
        {'name': 'moderator', 'description': 'Moderator role'}
    ]
    
    success_count = 0
    for role_data in roles:
        try:
            sql = '''
                INSERT INTO role (name, description)
                VALUES (%(name)s, %(description)s)
                ON CONFLICT (name) DO NOTHING
            '''
            
            with connection.cursor() as cursor:
                cursor.execute(sql, {
                    'name': role_data['name'],
                    'description': role_data['description']
                })
            
            print('[OK] Role created: {0}'.format(role_data['name']))
            success_count += 1
        except Exception as e:
            print('[ERROR] Failed to create role {0}: {1}'.format(
                role_data['name'], str(e)))
    
    return success_count


def init_permissions():
    """Initialize default permissions using raw SQL."""
    print('[INFO] Creating default permissions...')
    
    permissions = [
        {'name': 'CREATE_USER', 'description': 'Can create users'},
        {'name': 'READ_USER', 'description': 'Can read user data'},
        {'name': 'UPDATE_USER', 'description': 'Can update users'},
        {'name': 'DELETE_USER', 'description': 'Can delete users'},
        {'name': 'CREATE_ROLE', 'description': 'Can create roles'},
        {'name': 'READ_ROLE', 'description': 'Can read role data'},
        {'name': 'UPDATE_ROLE', 'description': 'Can update roles'},
        {'name': 'DELETE_ROLE', 'description': 'Can delete roles'}
    ]
    
    success_count = 0
    for perm_data in permissions:
        try:
            sql = '''
                INSERT INTO permission (name, description)
                VALUES (%(name)s, %(description)s)
                ON CONFLICT (name) DO NOTHING
            '''
            
            with connection.cursor() as cursor:
                cursor.execute(sql, {
                    'name': perm_data['name'],
                    'description': perm_data['description']
                })
            
            print('[OK] Permission created: {0}'.format(perm_data['name']))
            success_count += 1
        except Exception as e:
            print('[ERROR] Failed to create permission {0}: {1}'.format(
                perm_data['name'], str(e)))
    
    return success_count


if __name__ == '__main__':
    print('')
    print('=== Aura Auth Service Database Initialization ===')
    print('')
    
    init_admin_user()
    init_roles()
    init_permissions()
    
    print('')
    print('[OK] Initialization complete.')
    print('')
