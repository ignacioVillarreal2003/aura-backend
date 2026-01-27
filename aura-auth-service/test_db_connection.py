#!/usr/bin/env python
# -*- coding: utf-8 -*-

import django
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.configuration.settings')

BASE_DIR = os.path.dirname(__file__)
sys.path.insert(0, BASE_DIR)

django.setup()

from django.db import connection

print('Testing database connection...')

try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT version();')
        result = cursor.fetchone()
        print('[OK] Database version:', result[0][:50])
        print('[OK] Connection successful!')
except Exception as e:
    print('[ERROR] Connection failed:', str(e))
