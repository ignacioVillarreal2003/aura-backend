-- Migración manual: agrega la tabla audit_log a auth_db existente.
-- Ejecutar una sola vez sobre el contenedor ya levantado:
--   docker exec -it <auth-db-container> psql -U <user> -d <db> -f /path/to/migrate_audit_log.sql
-- o bien:
--   psql -h localhost -p 5433 -U <user> -d <db> < migrate_audit_log.sql

CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL       PRIMARY KEY,
    timestamp       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    actor_id        BIGINT,
    actor_username  VARCHAR(255),
    action          VARCHAR(20)     NOT NULL,
    entity_type     VARCHAR(100)    NOT NULL,
    entity_id       VARCHAR(255),
    entity_label    VARCHAR(255),
    details         JSONB,
    source          VARCHAR(20)     NOT NULL DEFAULT 'admin'
);

CREATE INDEX IF NOT EXISTS audit_log_timestamp_idx   ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS audit_log_actor_id_idx    ON audit_log(actor_id);
CREATE INDEX IF NOT EXISTS audit_log_entity_type_idx ON audit_log(entity_type);
CREATE INDEX IF NOT EXISTS audit_log_action_idx      ON audit_log(action);
