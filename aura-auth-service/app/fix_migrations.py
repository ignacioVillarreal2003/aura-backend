#!/usr/bin/env python
import psycopg2
from psycopg2 import sql

try:
    conn = psycopg2.connect(
        host='localhost',
        port=5433,
        database='auth_db',
        user='aura_root',
        password='aura_password'
    )
    
    with conn.cursor() as cur:
        # Read and execute the SQL file
        with open('fix_migrations.sql', 'r') as f:
            sql_commands = f.read()
        
        cur.execute(sql_commands)
        conn.commit()
    
    conn.close()
    print('[OK] Migration records inserted successfully')
    
except Exception as e:
    print(f'[ERROR] {str(e)}')
    exit(1)
