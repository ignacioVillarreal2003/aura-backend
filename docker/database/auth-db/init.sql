CREATE TYPE user_status AS ENUM ('active', 'inactive');

CREATE TABLE auth_user (
    id                      SERIAL PRIMARY KEY,
    username                VARCHAR(255)    NOT NULL UNIQUE,
    email                   VARCHAR(255)    NOT NULL UNIQUE,
    password                VARCHAR(255)    NOT NULL,
    status                  user_status     NOT NULL,
    last_login              TIMESTAMP,
    account_non_expired     BOOLEAN         NOT NULL DEFAULT TRUE,
    account_non_locked      BOOLEAN         NOT NULL DEFAULT TRUE,
    failed_login_attempts   INTEGER,
    lockout_until           TIMESTAMP,
    credentials_non_expired BOOLEAN         NOT NULL DEFAULT TRUE,
    last_password_change    TIMESTAMP,
    enabled                 BOOLEAN         NOT NULL DEFAULT TRUE,
    refresh_token           UUID,
    created_by              BIGINT          NOT NULL,
    created_at              TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_by              BIGINT,
    updated_at              TIMESTAMP,
    deleted_by              BIGINT,
    deleted_at              TIMESTAMP,
    CONSTRAINT fk_auth_user_created_by FOREIGN KEY (created_by) REFERENCES auth_user(id),
    CONSTRAINT fk_auth_user_updated_by FOREIGN KEY (updated_by) REFERENCES auth_user(id),
    CONSTRAINT fk_auth_user_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth_user(id)
);

CREATE TABLE role (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255)    NOT NULL UNIQUE,
    description VARCHAR(255)    NOT NULL
);

CREATE TABLE auth_user_in_role (
    id          SERIAL PRIMARY KEY,
    auth_user_id BIGINT         NOT NULL REFERENCES auth_user(id),
    role_id     BIGINT          NOT NULL REFERENCES role(id),
    created_by  BIGINT          NOT NULL REFERENCES auth_user(id),
    created_at  DATE            NOT NULL DEFAULT CURRENT_DATE,
    deleted_by  BIGINT          REFERENCES auth_user(id),
    deleted_at  TIMESTAMP
);

CREATE TABLE permission (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255)    NOT NULL UNIQUE,
    description VARCHAR(255)
);

CREATE TABLE permission_in_role (
    id          SERIAL PRIMARY KEY,
    role_id     BIGINT          NOT NULL REFERENCES role(id),
    permission_id BIGINT        NOT NULL REFERENCES permission(id),
    CONSTRAINT permission_in_role_unique UNIQUE (role_id, permission_id)
);

CREATE TABLE audit_log (
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

CREATE TABLE refresh_tokens (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    token       VARCHAR(255)    NOT NULL UNIQUE,
    is_revoked  BOOLEAN         NOT NULL DEFAULT FALSE,
    expires_at  TIMESTAMPTZ     NOT NULL,
    ip_address  INET,
    user_agent  TEXT            NOT NULL DEFAULT '',
    user_id     BIGINT          NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_by  BIGINT,
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    deleted_by  BIGINT
);

CREATE INDEX audit_log_timestamp_idx    ON audit_log(timestamp DESC);
CREATE INDEX audit_log_actor_id_idx     ON audit_log(actor_id);
CREATE INDEX audit_log_entity_type_idx  ON audit_log(entity_type);
CREATE INDEX audit_log_action_idx       ON audit_log(action);

CREATE INDEX refresh_tokens_user_idx        ON refresh_tokens(user_id);
CREATE INDEX refresh_tokens_is_revoked_idx  ON refresh_tokens(is_revoked);
CREATE INDEX refresh_tokens_expires_at_idx  ON refresh_tokens(expires_at);
CREATE INDEX refresh_tokens_user_active_idx ON refresh_tokens (user_id, expires_at)
    WHERE (NOT is_revoked AND deleted_at IS NULL);

CREATE INDEX auth_user_in_role_user_idx     ON auth_user_in_role (auth_user_id) WHERE (deleted_at IS NULL);
CREATE INDEX auth_user_in_role_role_idx     ON auth_user_in_role (role_id) WHERE (deleted_at IS NULL);
CREATE UNIQUE INDEX auth_user_in_role_user_role_active_uq
    ON auth_user_in_role (auth_user_id, role_id) WHERE (deleted_at IS NULL);

CREATE INDEX audit_log_entity_idx           ON audit_log (entity_type, entity_id);
CREATE INDEX audit_log_actor_time_idx        ON audit_log (actor_id, timestamp DESC);

INSERT INTO permission (name, description) VALUES
    ('INGEST_DOCUMENT', 'Ingerir o subir un documento al pipeline (carga e ingesta)'),
    ('GET_DOCUMENT', 'Ver el detalle de un documento'),
    ('LIST_DOCUMENTS', 'Listar documentos en general'),
    ('LIST_DOCUMENTS_BY_CHAT', 'Listar documentos asociados a un chat'),
    ('DOWNLOAD_DOCUMENT', 'Descargar el archivo de un documento'),
    ('SOFT_DELETE_DOCUMENT', 'Eliminar lógicamente (soft delete) un documento'),
    ('SOFT_DELETE_DOCUMENTS_BY_CHAT', 'Eliminar lógicamente documentos de un chat'),
    ('POST_PROCESS_DOCUMENTS_START_ALL', 'Iniciar el post-proceso masivo de documentos'),
    ('POST_PROCESS_DOCUMENTS_START', 'Iniciar el post-proceso de un documento concreto'),
    ('POST_PROCESS_DOCUMENTS_STATUS', 'Consultar el estado del post-proceso de documentos'),
    ('POST_PROCESS_DOCUMENTS_STOP', 'Detener el post-proceso de documentos'),
    ('POST_PROCESS_FRAGMENTS_START_ALL', 'Iniciar el post-proceso masivo de fragmentos'),
    ('POST_PROCESS_FRAGMENTS_START', 'Iniciar el post-proceso de un fragmento o lote'),
    ('POST_PROCESS_FRAGMENTS_STATUS', 'Consultar el estado del post-proceso de fragmentos'),
    ('POST_PROCESS_FRAGMENTS_STOP', 'Detener el post-proceso de fragmentos'),
    ('LIST_CONTEXT_FRAGMENTS_BY_QUESTION', 'Obtener fragmentos de contexto según una pregunta'),
    ('LIST_CONTEXT_FRAGMENTS_BY_DOCUMENTS', 'Obtener fragmentos de contexto a partir de documentos'),
    ('LIST_DOCUMENT_COLLECTIONS', 'Listar conjuntos o grupos de documentos'),
    ('CREATE_DOCUMENT_COLLECTION', 'Crear un conjunto de documentos'),
    ('GET_DOCUMENT_COLLECTION', 'Ver el detalle de un conjunto de documentos'),
    ('UPDATE_DOCUMENT_COLLECTION', 'Modificar un conjunto de documentos'),
    ('DELETE_DOCUMENT_COLLECTION', 'Eliminar un conjunto de documentos'),
    ('LIST_DOCUMENT_COLLECTION_USERS', 'Listar usuarios asignados a un conjunto'),
    ('ADD_DOCUMENT_COLLECTION_USER', 'Añadir un usuario a un conjunto de documentos'),
    ('REMOVE_DOCUMENT_COLLECTION_USER', 'Quitar un usuario de un conjunto de documentos'),
    ('LIST_DOCUMENT_COLLECTION_DOCUMENTS', 'Listar documentos incluidos en un conjunto'),
    ('ADD_DOCUMENT_COLLECTION_DOCUMENT', 'Añadir un documento a un conjunto'),
    ('REMOVE_DOCUMENT_COLLECTION_DOCUMENT', 'Quitar un documento de un conjunto');

INSERT INTO role (name, description) VALUES
    ('superadmin', 'Super administrador con acceso total'),
    ('admin',      'Administrador con acceso de gestión'),
    ('user',       'Usuario estándar del sistema');

INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r, permission p
WHERE r.name = 'superadmin';

INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r, permission p
WHERE r.name = 'admin';

INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r, permission p
WHERE r.name = 'user'
AND p.name IN (
    'SOFT_DELETE_DOCUMENTS_BY_CHAT',
    'LIST_CONTEXT_FRAGMENTS_BY_QUESTION',
    'LIST_CONTEXT_FRAGMENTS_BY_DOCUMENTS',
    'INGEST_DOCUMENT'
);


INSERT INTO auth_user (
    username, email, password, status,
    account_non_expired, account_non_locked, credentials_non_expired,
    enabled, failed_login_attempts,
    created_by, created_at
) VALUES
    (
        'gral.rodriguez',
        'rodriguez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    ),
    (
        'como.martinez',
        'martinez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    ),
    (
        'cap.gonzalez',
        'gonzalez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    ),
    (
        'ten.lopez',
        'lopez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    ),
    (
        'cabo.perez',
        'perez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    ),
    (
        'sold.garcia',
        'garcia@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    );

INSERT INTO auth_user_in_role (auth_user_id, role_id, created_by, created_at) VALUES
    (
        (SELECT id FROM auth_user WHERE username = 'gral.rodriguez'),
        (SELECT id FROM role WHERE name = 'superadmin'),
        1, NOW()
    ),
    (
        (SELECT id FROM auth_user WHERE username = 'como.martinez'),
        (SELECT id FROM role WHERE name = 'admin'),
        1, NOW()
    ),
    (
        (SELECT id FROM auth_user WHERE username = 'cap.gonzalez'),
        (SELECT id FROM role WHERE name = 'admin'),
        1, NOW()
    ),
    (
        (SELECT id FROM auth_user WHERE username = 'ten.lopez'),
        (SELECT id FROM role WHERE name = 'user'),
        1, NOW()
    ),
    (
        (SELECT id FROM auth_user WHERE username = 'cabo.perez'),
        (SELECT id FROM role WHERE name = 'user'),
        1, NOW()
    ),
    (
        (SELECT id FROM auth_user WHERE username = 'sold.garcia'),
        (SELECT id FROM role WHERE name = 'user'),
        1, NOW()
    );
