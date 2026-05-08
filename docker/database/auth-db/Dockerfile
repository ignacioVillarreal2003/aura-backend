FROM postgres:17

RUN apt-get update && apt-get install -y postgresql-17-pgvector && rm -rf /var/lib/apt/lists/*

COPY init.sql /docker-entrypoint-initdb.d/01-init.sql
COPY data.sql /docker-entrypoint-initdb.d/02-data.sql
