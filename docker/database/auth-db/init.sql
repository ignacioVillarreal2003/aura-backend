CREATE TYPE user_status AS ENUM ('active', 'inactive');

CREATE TABLE auth_user
(
    id                      SERIAL PRIMARY KEY,
    username                VARCHAR(255) NOT NULL UNIQUE,
    name                    VARCHAR(255),
    email                   VARCHAR(255) NOT NULL UNIQUE,
    password                VARCHAR(255) NOT NULL,
    status                  user_status  NOT NULL,
    last_login              TIMESTAMP,
    account_non_expired     BOOLEAN      NOT NULL DEFAULT TRUE,
    account_non_locked      BOOLEAN      NOT NULL DEFAULT TRUE,
    failed_login_attempts   INTEGER,
    lockout_until           TIMESTAMP,
    credentials_non_expired BOOLEAN      NOT NULL DEFAULT TRUE,
    last_password_change    TIMESTAMP,
    enabled                 BOOLEAN      NOT NULL DEFAULT TRUE,
    refresh_token           UUID,
    force_logout_at         TIMESTAMPTZ,
    created_by              BIGINT       NOT NULL,
    created_at              TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_by              BIGINT,
    updated_at              TIMESTAMP,
    deleted_by              BIGINT,
    deleted_at              TIMESTAMP,
    CONSTRAINT fk_auth_user_created_by FOREIGN KEY (created_by) REFERENCES auth_user (id),
    CONSTRAINT fk_auth_user_updated_by FOREIGN KEY (updated_by) REFERENCES auth_user (id),
    CONSTRAINT fk_auth_user_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth_user (id)
);

CREATE TABLE role
(
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL UNIQUE,
    description VARCHAR(255) NOT NULL
);

CREATE TABLE auth_user_in_role
(
    id           SERIAL PRIMARY KEY,
    auth_user_id BIGINT NOT NULL REFERENCES auth_user (id),
    role_id      BIGINT NOT NULL REFERENCES role (id),
    created_by   BIGINT NOT NULL REFERENCES auth_user (id),
    created_at   DATE   NOT NULL DEFAULT CURRENT_DATE,
    deleted_by   BIGINT REFERENCES auth_user (id),
    deleted_at   TIMESTAMP
);

CREATE TABLE permission
(
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL UNIQUE,
    description VARCHAR(255)
);

CREATE TABLE permission_in_role
(
    id            SERIAL PRIMARY KEY,
    role_id       BIGINT NOT NULL REFERENCES role (id),
    permission_id BIGINT NOT NULL REFERENCES permission (id),
    CONSTRAINT permission_in_role_unique UNIQUE (role_id, permission_id)
);

CREATE TABLE audit_log
(
    id             BIGSERIAL PRIMARY KEY,
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    actor_id       BIGINT,
    actor_username VARCHAR(255),
    action         VARCHAR(20)  NOT NULL,
    entity_type    VARCHAR(100) NOT NULL,
    entity_id      VARCHAR(255),
    entity_label   VARCHAR(255),
    details        JSONB,
    source         VARCHAR(20)  NOT NULL DEFAULT 'admin'
);

CREATE TABLE refresh_tokens
(
    id         UUID PRIMARY KEY      DEFAULT gen_random_uuid(),
    token      VARCHAR(255) NOT NULL UNIQUE,
    is_revoked BOOLEAN      NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ  NOT NULL,
    ip_address INET,
    user_agent TEXT         NOT NULL DEFAULT '',
    user_id    BIGINT       NOT NULL REFERENCES auth_user (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by BIGINT,
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by BIGINT,
    deleted_at TIMESTAMPTZ,
    deleted_by BIGINT
);

CREATE INDEX audit_log_timestamp_idx ON audit_log (timestamp DESC);
CREATE INDEX audit_log_actor_id_idx ON audit_log (actor_id);
CREATE INDEX audit_log_entity_type_idx ON audit_log (entity_type);
CREATE INDEX audit_log_action_idx ON audit_log (action);

CREATE INDEX refresh_tokens_user_idx ON refresh_tokens (user_id);
CREATE INDEX refresh_tokens_is_revoked_idx ON refresh_tokens (is_revoked);
CREATE INDEX refresh_tokens_expires_at_idx ON refresh_tokens (expires_at);
CREATE INDEX refresh_tokens_user_active_idx ON refresh_tokens (user_id, expires_at) WHERE (NOT is_revoked AND deleted_at IS NULL);

CREATE INDEX auth_user_in_role_user_idx ON auth_user_in_role (auth_user_id) WHERE (deleted_at IS NULL);
CREATE INDEX auth_user_in_role_role_idx ON auth_user_in_role (role_id) WHERE (deleted_at IS NULL);
CREATE UNIQUE INDEX auth_user_in_role_user_role_active_uq
    ON auth_user_in_role (auth_user_id, role_id) WHERE (deleted_at IS NULL);

CREATE INDEX audit_log_entity_idx ON audit_log (entity_type, entity_id);
CREATE INDEX audit_log_actor_time_idx ON audit_log (actor_id, timestamp DESC);
