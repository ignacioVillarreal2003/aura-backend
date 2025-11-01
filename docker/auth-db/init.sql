CREATE TYPE user_status AS ENUM ('active', 'inactive');

CREATE TABLE auth_user (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    status user_status NOT NULL,
    last_login TIMESTAMP,
    account_non_expired BOOLEAN NOT NULL,
    account_non_locked BOOLEAN NOT NULL,
    failed_login_attempts INT,
    lockout_until TIMESTAMP,
    credentials_non_expired BOOLEAN NOT NULL,
    last_password_change TIMESTAMP,
    enabled BOOLEAN NOT NULL,
    refresh_token UUID,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_by BIGINT,
    updated_at TIMESTAMP,
    deleted_by BIGINT,
    deleted_at TIMESTAMP,
    CONSTRAINT fk_auth_user_created_by FOREIGN KEY (created_by) REFERENCES "auth_user"(id),
    CONSTRAINT fk_auth_user_updated_by FOREIGN KEY (updated_by) REFERENCES "auth_user"(id),
    CONSTRAINT fk_auth_user_deleted_by FOREIGN KEY (deleted_by) REFERENCES "auth_user"(id)
);

CREATE TABLE role (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(255) NOT NULL
);

CREATE TABLE auth_user_in_role (
    id SERIAL PRIMARY KEY,
    auth_user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,
    created_at DATE NOT NULL,
    deleted_by BIGINT,
    deleted_at TIMESTAMP,
    CONSTRAINT fk_auth_user_in_role_created_by FOREIGN KEY (created_by) REFERENCES "auth_user"(id),
    CONSTRAINT fk_auth_user_in_role_deleted_by FOREIGN KEY (deleted_by) REFERENCES "auth_user"(id)
);

CREATE TABLE permission (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(255)
);

CREATE TABLE permission_in_role (
    id SERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL,
    permission_id BIGINT NOT NULL,
    CONSTRAINT fk_permission_in_role_role_id FOREIGN KEY (role_id) REFERENCES "role"(id),
    CONSTRAINT fk_permission_in_role_permission_id FOREIGN KEY (permission_id) REFERENCES "permission"(id)
);




