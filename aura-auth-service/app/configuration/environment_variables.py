from decouple import config

# Database Configuration
DATABASE_ENGINE = config('DATABASE_ENGINE', default='django.db.backends.postgresql')
DATABASE_HOST = config('DATABASE_HOST', default='localhost')
DATABASE_PORT = config('DATABASE_PORT', default='5433', cast=int)
DATABASE_NAME = config('DATABASE_NAME', default='auth_db')
DATABASE_USER = config('DATABASE_USER', default='aura_root')
DATABASE_PASSWORD = config('DATABASE_PASSWORD', default='aura_password')

# Django Settings
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')
SECRET_KEY = config('SECRET_KEY', default='django-insecure-development-key')

# CORS Settings
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://localhost:8000').split(',')

# Logging
LOG_LEVEL = config('LOG_LEVEL', default='INFO')
