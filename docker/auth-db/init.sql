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
    ('documentos.ver',                  'Ver documentos del sistema'),
    ('documentos.cargar',               'Cargar nuevos documentos'),
    ('documentos.eliminar',             'Eliminar documentos'),
    ('documentos.gestionar_colecciones','Gestionar colecciones de documentos'),
    ('usuarios.ver',                    'Ver listado de usuarios'),
    ('usuarios.crear',                  'Crear nuevos usuarios'),
    ('usuarios.editar',                 'Editar usuarios existentes'),
    ('usuarios.eliminar',               'Eliminar usuarios'),
    ('chat.usar',                       'Usar el chat con el asistente'),
    ('chat.ver_historial',              'Ver historial de conversaciones'),
    ('chat.gestionar',                  'Gestionar salas de chat'),
    ('notificaciones.ver',              'Ver notificaciones propias'),
    ('notificaciones.enviar',           'Enviar notificaciones a usuarios'),
    ('sistema.administrar',             'Administrar configuración del sistema'),
    ('sistema.ver_auditoria',           'Ver logs y auditoría del sistema');

-- ============================================
-- FAU ROLES (rangos Fuerza Aérea)
-- ============================================
INSERT INTO fau_role (name, description, power) VALUES
    ('General de Brigada',    'Máxima autoridad institucional',         600),
    ('Comodoro',              'Alto mando operativo',                   500),
    ('Vicecomodoro',          'Segundo al mando operativo',             400),
    ('Mayor',                 'Oficial superior de área',               350),
    ('Capitán',               'Oficial a cargo de unidad',              300),
    ('Teniente Primero',      'Oficial de apoyo senior',                250),
    ('Teniente',              'Oficial de apoyo',                       200),
    ('Subteniente',           'Oficial en formación',                   150),
    ('Suboficial Mayor',      'Suboficial de mayor jerarquía',          120),
    ('Cabo Primero',          'Suboficial intermedio',                   80),
    ('Cabo',                  'Suboficial básico',                       50),
    ('Soldado',               'Personal de tropa',                       10);

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
-- PERMISOS POR FAU ROLE
-- ============================================

-- General de Brigada y Comodoro    : todos los permisos
INSERT INTO permission_in_fau_role (fau_role_id, permission_id)
SELECT fr.id, p.id
FROM fau_role fr, permission p
WHERE fr.name IN ('General de Brigada', 'Comodoro');

-- Mayor, Capitán, Vicecomodoro: gestión documental + chat completo
INSERT INTO permission_in_fau_role (fau_role_id, permission_id)
SELECT fr.id, p.id
FROM fau_role fr, permission p
WHERE fr.name IN ('Vicecomodoro', 'Mayor', 'Capitán')
AND p.name IN (
    'documentos.ver',
    'documentos.cargar',
    'documentos.gestionar_colecciones',
    'chat.usar',
    'chat.ver_historial',
    'chat.gestionar',
    'notificaciones.ver',
    'notificaciones.enviar',
    'sistema.ver_auditoria'
);

-- Teniente Primero, Teniente, Subteniente: documentos + chat básico
INSERT INTO permission_in_fau_role (fau_role_id, permission_id)
SELECT fr.id, p.id
FROM fau_role fr, permission p
WHERE fr.name IN ('Teniente Primero', 'Teniente', 'Subteniente')
AND p.name IN (
    'documentos.ver',
    'documentos.cargar',
    'chat.usar',
    'chat.ver_historial',
    'notificaciones.ver'
);

-- Suboficial Mayor, Cabo Primero, Cabo, Soldado: solo lectura
INSERT INTO permission_in_fau_role (fau_role_id, permission_id)
SELECT fr.id, p.id
FROM fau_role fr, permission p
WHERE fr.name IN ('Suboficial Mayor', 'Cabo Primero', 'Cabo', 'Soldado')
AND p.name IN (
    'documentos.ver',
    'chat.usar',
    'notificaciones.ver'
);

-- ============================================
-- USUARIOS
-- ============================================
-- NOTA: passwords hasheados con Django's PBKDF2SHA256
-- Todos tienen password: Aura2024!
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
