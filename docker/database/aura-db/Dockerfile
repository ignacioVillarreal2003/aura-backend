FROM paradedb/paradedb:v0.23.2-pg17

COPY init.sql /docker-entrypoint-initdb.d/01-init.sql
COPY data.sql /docker-entrypoint-initdb.d/02-data.sql
