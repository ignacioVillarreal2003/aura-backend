CREATE TYPE user_status AS ENUM ('active', 'inactive');

CREATE TABLE fau_role (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255)    NOT NULL UNIQUE,
    description VARCHAR(255)    NOT NULL DEFAULT '',
    power       INTEGER         UNIQUE
);

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
    fau_role_id             INTEGER         REFERENCES fau_role(id) ON DELETE SET NULL,
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
    name        VARCHAR(255)    NOT NULL,
    description VARCHAR(255)
);

CREATE TABLE permission_in_role (
    id          SERIAL PRIMARY KEY,
    role_id     BIGINT          NOT NULL REFERENCES role(id),
    permission_id BIGINT        NOT NULL REFERENCES permission(id)
);

CREATE TABLE permission_in_fau_role (
    id          SERIAL PRIMARY KEY,
    fau_role_id BIGINT          NOT NULL REFERENCES fau_role(id),
    permission_id BIGINT        NOT NULL REFERENCES permission(id),
    CONSTRAINT permission_in_fau_role_unique UNIQUE (fau_role_id, permission_id)
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

CREATE INDEX audit_log_timestamp_idx    ON audit_log(timestamp DESC);
CREATE INDEX audit_log_actor_id_idx     ON audit_log(actor_id);
CREATE INDEX audit_log_entity_type_idx  ON audit_log(entity_type);
CREATE INDEX audit_log_action_idx       ON audit_log(action);

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

CREATE INDEX refresh_tokens_user_idx        ON refresh_tokens(user_id);
CREATE INDEX refresh_tokens_token_idx       ON refresh_tokens(token);
CREATE INDEX refresh_tokens_is_revoked_idx  ON refresh_tokens(is_revoked);
CREATE INDEX refresh_tokens_expires_at_idx  ON refresh_tokens(expires_at);


-- datos de prueba

-- ============================================
-- PERMISOS
-- ============================================
INSERT INTO permission (name, description) VALUES
-- fau_role
('FAU_ROLE_CREATE', 'Permite crear registros de fau_role'),
('FAU_ROLE_GET', 'Permite consultar registros de fau_role'),
('FAU_ROLE_UPDATE', 'Permite actualizar registros de fau_role'),
('FAU_ROLE_DELETE', 'Permite eliminar registros de fau_role'),

-- auth_user
('AUTH_USER_CREATE', 'Permite crear registros de auth_user'),
('AUTH_USER_GET', 'Permite consultar registros de auth_user'),
('AUTH_USER_UPDATE', 'Permite actualizar registros de auth_user'),
('AUTH_USER_DELETE', 'Permite eliminar registros de auth_user'),

-- role
('ROLE_CREATE', 'Permite crear registros de role'),
('ROLE_GET', 'Permite consultar registros de role'),
('ROLE_UPDATE', 'Permite actualizar registros de role'),
('ROLE_DELETE', 'Permite eliminar registros de role'),

-- auth_user_in_role
('AUTH_USER_IN_ROLE_CREATE', 'Permite crear registros de auth_user_in_role'),
('AUTH_USER_IN_ROLE_GET', 'Permite consultar registros de auth_user_in_role'),
('AUTH_USER_IN_ROLE_UPDATE', 'Permite actualizar registros de auth_user_in_role'),
('AUTH_USER_IN_ROLE_DELETE', 'Permite eliminar registros de auth_user_in_role'),

-- permission
('PERMISSION_CREATE', 'Permite crear registros de permission'),
('PERMISSION_GET', 'Permite consultar registros de permission'),
('PERMISSION_UPDATE', 'Permite actualizar registros de permission'),
('PERMISSION_DELETE', 'Permite eliminar registros de permission'),

-- permission_in_role
('PERMISSION_IN_ROLE_CREATE', 'Permite crear registros de permission_in_role'),
('PERMISSION_IN_ROLE_GET', 'Permite consultar registros de permission_in_role'),
('PERMISSION_IN_ROLE_UPDATE', 'Permite actualizar registros de permission_in_role'),
('PERMISSION_IN_ROLE_DELETE', 'Permite eliminar registros de permission_in_role'),

-- permission_in_fau_role
('PERMISSION_IN_FAU_ROLE_CREATE', 'Permite crear registros de permission_in_fau_role'),
('PERMISSION_IN_FAU_ROLE_GET', 'Permite consultar registros de permission_in_fau_role'),
('PERMISSION_IN_FAU_ROLE_UPDATE', 'Permite actualizar registros de permission_in_fau_role'),
('PERMISSION_IN_FAU_ROLE_DELETE', 'Permite eliminar registros de permission_in_fau_role'),

-- refresh_tokens
('REFRESH_TOKENS_CREATE', 'Permite crear registros de refresh_tokens'),
('REFRESH_TOKENS_GET', 'Permite consultar registros de refresh_tokens'),
('REFRESH_TOKENS_UPDATE', 'Permite actualizar registros de refresh_tokens'),
('REFRESH_TOKENS_DELETE', 'Permite eliminar registros de refresh_tokens'),

-- chat
('CHAT_CREATE', 'Permite crear registros de chat'),
('CHAT_GET', 'Permite consultar registros de chat'),
('CHAT_UPDATE', 'Permite actualizar registros de chat'),
('CHAT_DELETE', 'Permite eliminar registros de chat'),

-- document
('DOCUMENT_CREATE', 'Permite crear registros de document'),
('DOCUMENT_GET', 'Permite consultar registros de document'),
('DOCUMENT_UPDATE', 'Permite actualizar registros de document'),
('DOCUMENT_DELETE', 'Permite eliminar registros de document'),

-- fragment
('FRAGMENT_CREATE', 'Permite crear registros de fragment'),
('FRAGMENT_GET', 'Permite consultar registros de fragment'),
('FRAGMENT_UPDATE', 'Permite actualizar registros de fragment'),
('FRAGMENT_DELETE', 'Permite eliminar registros de fragment'),

-- chat_message
('CHAT_MESSAGE_CREATE', 'Permite crear registros de chat_message'),
('CHAT_MESSAGE_GET', 'Permite consultar registros de chat_message'),
('CHAT_MESSAGE_UPDATE', 'Permite actualizar registros de chat_message'),
('CHAT_MESSAGE_DELETE', 'Permite eliminar registros de chat_message'),

-- chat_membership
('CHAT_MEMBERSHIP_CREATE', 'Permite crear registros de chat_membership'),
('CHAT_MEMBERSHIP_GET', 'Permite consultar registros de chat_membership'),
('CHAT_MEMBERSHIP_UPDATE', 'Permite actualizar registros de chat_membership'),
('CHAT_MEMBERSHIP_DELETE', 'Permite eliminar registros de chat_membership'),

-- notification
('NOTIFICATION_CREATE', 'Permite crear registros de notification'),
('NOTIFICATION_GET', 'Permite consultar registros de notification'),
('NOTIFICATION_UPDATE', 'Permite actualizar registros de notification'),
('NOTIFICATION_DELETE', 'Permite eliminar registros de notification'),

-- document_collection
('DOCUMENT_COLLECTION_CREATE', 'Permite crear registros de document_collection'),
('DOCUMENT_COLLECTION_GET', 'Permite consultar registros de document_collection'),
('DOCUMENT_COLLECTION_UPDATE', 'Permite actualizar registros de document_collection'),
('DOCUMENT_COLLECTION_DELETE', 'Permite eliminar registros de document_collection'),

-- document_in_document_collection
('DOCUMENT_IN_DOCUMENT_COLLECTION_CREATE', 'Permite crear registros de document_in_document_collection'),
('DOCUMENT_IN_DOCUMENT_COLLECTION_GET', 'Permite consultar registros de document_in_document_collection'),
('DOCUMENT_IN_DOCUMENT_COLLECTION_UPDATE', 'Permite actualizar registros de document_in_document_collection'),
('DOCUMENT_IN_DOCUMENT_COLLECTION_DELETE', 'Permite eliminar registros de document_in_document_collection'),

-- user_in_document_collection
('USER_IN_DOCUMENT_COLLECTION_CREATE', 'Permite crear registros de user_in_document_collection'),
('USER_IN_DOCUMENT_COLLECTION_GET', 'Permite consultar registros de user_in_document_collection'),
('USER_IN_DOCUMENT_COLLECTION_UPDATE', 'Permite actualizar registros de user_in_document_collection'),
('USER_IN_DOCUMENT_COLLECTION_DELETE', 'Permite eliminar registros de user_in_document_collection'),

-- custom_groups
('CUSTOM_GROUPS_CREATE', 'Permite crear registros de custom_groups'),
('CUSTOM_GROUPS_GET', 'Permite consultar registros de custom_groups'),
('CUSTOM_GROUPS_UPDATE', 'Permite actualizar registros de custom_groups'),
('CUSTOM_GROUPS_DELETE', 'Permite eliminar registros de custom_groups'),

-- documents
('DOCUMENTS_CREATE', 'Permite crear registros de documents'),
('DOCUMENTS_GET', 'Permite consultar registros de documents'),
('DOCUMENTS_UPDATE', 'Permite actualizar registros de documents'),
('DOCUMENTS_DELETE', 'Permite eliminar registros de documents'),

-- document_roles
('DOCUMENT_ROLES_CREATE', 'Permite crear registros de document_roles'),
('DOCUMENT_ROLES_GET', 'Permite consultar registros de document_roles'),
('DOCUMENT_ROLES_UPDATE', 'Permite actualizar registros de document_roles'),
('DOCUMENT_ROLES_DELETE', 'Permite eliminar registros de document_roles'),

-- auth_user_custom_groups
('AUTH_USER_CUSTOM_GROUPS_CREATE', 'Permite crear registros de auth_user_custom_groups'),
('AUTH_USER_CUSTOM_GROUPS_GET', 'Permite consultar registros de auth_user_custom_groups'),
('AUTH_USER_CUSTOM_GROUPS_UPDATE', 'Permite actualizar registros de auth_user_custom_groups'),
('AUTH_USER_CUSTOM_GROUPS_DELETE', 'Permite eliminar registros de auth_user_custom_groups'),

-- custom_groups_documents
('CUSTOM_GROUPS_DOCUMENTS_CREATE', 'Permite crear registros de custom_groups_documents'),
('CUSTOM_GROUPS_DOCUMENTS_GET', 'Permite consultar registros de custom_groups_documents'),
('CUSTOM_GROUPS_DOCUMENTS_UPDATE', 'Permite actualizar registros de custom_groups_documents'),
('CUSTOM_GROUPS_DOCUMENTS_DELETE', 'Permite eliminar registros de custom_groups_documents');

-- ============================================
-- FAU ROLES (rangos Fuerza Aérea)
-- ============================================
INSERT INTO fau_role (name, description, power) VALUES
    ('General de Brigada',    'Máxima autoridad institucional',         12),
    ('Comodoro',              'Alto mando operativo',                   11),
    ('Vicecomodoro',          'Segundo al mando operativo',             10),
    ('Mayor',                 'Oficial superior de área',                9),
    ('Capitán',               'Oficial a cargo de unidad',               8),
    ('Teniente Primero',      'Oficial de apoyo senior',                 7),
    ('Teniente',              'Oficial de apoyo',                        6),
    ('Subteniente',           'Oficial en formación',                    5),
    ('Suboficial Mayor',      'Suboficial de mayor jerarquía',           4),
    ('Cabo Primero',          'Suboficial intermedio',                   3),
    ('Cabo',                  'Suboficial básico',                       2),
    ('Soldado',               'Personal de tropa',                       1);

-- ============================================
-- ROLES DEL SISTEMA
-- ============================================
INSERT INTO role (name, description) VALUES
    ('superadmin', 'Super administrador con acceso total'),
    ('admin',      'Administrador con acceso de gestión'),
    ('user',       'Usuario estándar del sistema')
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- PERMISOS POR ROL
-- ============================================

-- superadmin tiene todos los permisos
INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r, permission p
WHERE r.name = 'superadmin';

-- admin tiene casi todo menos sistema.administrar
INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r, permission p
WHERE r.name = 'admin'
AND p.name NOT IN ('sistema.administrar');

-- user tiene permisos básicos
INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r, permission p
WHERE r.name = 'user'
AND p.name IN (
    'documentos.ver',
    'chat.usar',
    'chat.ver_historial',
    'notificaciones.ver'
);

-- ============================================
-- USUARIOS
-- ============================================
-- NOTA: passwords hasheados con Django's PBKDF2SHA256
-- Todos tienen password: 
INSERT INTO auth_user (
    username, email, password, status,
    account_non_expired, account_non_locked, credentials_non_expired,
    enabled, failed_login_attempts,
    fau_role_id, created_by, created_at
) VALUES
    (
        'gral.rodriguez',
        'rodriguez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        (SELECT id FROM fau_role WHERE name = 'General de Brigada'),
        1, NOW()
    ),
    (
        'como.martinez',
        'martinez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        (SELECT id FROM fau_role WHERE name = 'Comodoro'),
        1, NOW()
    ),
    (
        'cap.gonzalez',
        'gonzalez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        (SELECT id FROM fau_role WHERE name = 'Capitán'),
        1, NOW()
    ),
    (
        'ten.lopez',
        'lopez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        (SELECT id FROM fau_role WHERE name = 'Teniente'),
        1, NOW()
    ),
    (
        'cabo.perez',
        'perez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        (SELECT id FROM fau_role WHERE name = 'Cabo'),
        1, NOW()
    ),
    (
        'sold.garcia',
        'garcia@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        (SELECT id FROM fau_role WHERE name = 'Soldado'),
        1, NOW()
    );

-- ============================================
-- ASIGNAR ROLES DEL SISTEMA A USUARIOS
-- ============================================
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
