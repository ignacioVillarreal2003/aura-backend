# Entorno

## Entorno local

Crear un archivo `.env` en la raíz del proyecto con todas las variables:

```env
# Base de datos
DB_HOST=localhost
DB_PORT=5432
DB_NAME=aura_db
DB_USER=aura_root
DB_PASSWORD=aura_password
DB_DRIVER=postgresql+psycopg2

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=aura_root
MINIO_SECRET_KEY=aura_password
MINIO_SECURE=false

# Generales
CLEANER_TYPE=full
SPLITTER_TYPE=semantic
EMBEDDER_TYPE=spacy
VECTOR_DIMENSION=96
SPLIT_SIZE=400
SPLIT_OVERLAP=50

MAX_FILE_SIZE_MB=20
ENVIRONMENT=development
```

## Entorno Docker

Crear un archivo `.env.docker` con las variables adaptadas a los servicios de Docker:

```env
# Base de datos
DB_HOST=db
DB_PORT=5432
DB_NAME=aura_db
DB_USER=aura_root
DB_PASSWORD=aura_password
DB_DRIVER=postgresql+psycopg2

# MinIO
MINIO_ENDPOINT=storage:9000
MINIO_ACCESS_KEY=aura_root
MINIO_SECRET_KEY=aura_password
MINIO_SECURE=false

# Generales
CLEANER_TYPE=full
SPLITTER_TYPE=semantic
EMBEDDER_TYPE=spacy
VECTOR_DIMENSION=96
SPLIT_SIZE=400
SPLIT_OVERLAP=50

MAX_FILE_SIZE_MB=20
ENVIRONMENT=docker
```
