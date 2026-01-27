#!/usr/bin/env python
# -*- coding: utf-8 -*-

import psycopg2
import sys

try:
    print('Attempting direct psycopg2 connection...')
    conn = psycopg2.connect(
        host='localhost',
        port=5433,
        database='auth_db',
        user='aura_root',
        password='aura_password',
        client_encoding='UTF8'
    )
    print('[OK] Connection successful!')
    
    with conn.cursor() as cur:
        cur.execute('SELECT version();')
        result = cur.fetchone()
        print('[OK] PostgreSQL version:', str(result[0])[:60])
    
    conn.close()
    
except Exception as e:
    print('[ERROR] Failed:', str(e))
    import traceback
    traceback.print_exc()
