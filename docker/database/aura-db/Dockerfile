FROM paradedb/paradedb:v0.23.2-pg17

COPY chat.sql /docker-entrypoint-initdb.d/01-chat.sql
COPY document_processing.sql /docker-entrypoint-initdb.d/02-document_processing.sql
COPY document_collection.sql /docker-entrypoint-initdb.d/03-document_collection.sql
COPY notification.sql /docker-entrypoint-initdb.d/04-notification.sql

EXPOSE 5432
