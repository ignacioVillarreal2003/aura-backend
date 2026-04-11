CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE document_type AS ENUM (
    'manual',
    'informe',
    'orden',
    'doctrina',
    'otro'
);

CREATE TYPE document_status AS ENUM (
    'uploaded',
    'processing',
    'processed',
    'failed'
);

CREATE TYPE document_mime_type AS ENUM (
    'pdf',
    'docx'
);

CREATE TYPE chat_message_sender_type AS ENUM (
    'system',
    'user'
);

CREATE TYPE chat_membership_status AS ENUM (
    'active',
    'inactive',
    'pending'
);

CREATE TYPE notification_type AS ENUM (
    'system',
    'admin'
);

CREATE TABLE chat (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(255)             NOT NULL,
    system_prompt TEXT,
    response_style TEXT,
    last_message_at TIMESTAMPTZ,
    created_by  BIGINT                   NOT NULL,
    created_at  TIMESTAMPTZ              NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ,
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE document (
    id                      BIGSERIAL PRIMARY KEY,
    chat_id                 BIGINT
        CONSTRAINT fk_document_chat_id REFERENCES chat(id) ON DELETE CASCADE,
    name                    VARCHAR(255)    NOT NULL,
    description             TEXT,
    mime_type               document_mime_type NOT NULL,
    status                  document_status NOT NULL DEFAULT 'uploaded',
    storage_url             VARCHAR(255)    NOT NULL,
    file_size_bytes         BIGINT          NOT NULL,
    type                    document_type,
    category                VARCHAR(255),
    text_cleaner_type       VARCHAR(255),
    text_splitter_type      VARCHAR(255),
    embedder_type           VARCHAR(255),
    split_size              INT,
    split_overlap           INT,
    processing_started_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    processing_finished_at  TIMESTAMPTZ,
    created_by              BIGINT          NOT NULL,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by              BIGINT,
    updated_at              TIMESTAMPTZ,
    deleted_by              BIGINT,
    deleted_at              TIMESTAMPTZ
);

CREATE TABLE fragment (
    id              BIGSERIAL PRIMARY KEY,
    document_id     BIGINT          NOT NULL
        REFERENCES document(id) ON DELETE CASCADE,
    content         TEXT            NOT NULL,
    vector          VECTOR          NOT NULL,
    fragment_index  INT             NOT NULL,
    summary         TEXT,
    entities        JSONB,
    topics          TEXT[],
    created_by      BIGINT          NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by      BIGINT,
    updated_at      TIMESTAMPTZ,
    deleted_by      BIGINT,
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE chat_message (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT                      NOT NULL
        CONSTRAINT fk_chat_message_chat_id REFERENCES chat(id),
    message     TEXT                        NOT NULL,
    sender_type chat_message_sender_type    NOT NULL,
    created_by  BIGINT,
    created_at  TIMESTAMPTZ                 NOT NULL DEFAULT NOW(),
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE chat_membership (
    id          BIGSERIAL PRIMARY KEY,
    member_id   BIGINT                  NOT NULL,
    chat_id     BIGINT                  NOT NULL
        CONSTRAINT fk_chat_membership_chat_id REFERENCES chat(id),
    status      chat_membership_status  NOT NULL,
    joined_at   TIMESTAMPTZ,
    left_at     TIMESTAMPTZ,
    created_by  BIGINT                  NOT NULL,
    created_at  TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ,
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT chat_membership_member_chat_unique UNIQUE (member_id, chat_id)
);

CREATE TABLE notification (
    id          BIGSERIAL PRIMARY KEY,
    receiver_id BIGINT              NOT NULL,
    message     VARCHAR(500)        NOT NULL,
    type        notification_type   NOT NULL,
    target_scope VARCHAR(20)        NOT NULL DEFAULT 'individual',
    target_label VARCHAR(255),
    status      VARCHAR(20)         NOT NULL DEFAULT 'unread',
    read_at     TIMESTAMPTZ,
    created_by  BIGINT,
    created_at  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ,
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE document_collection (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(255)    NOT NULL,
    created_by  BIGINT          NOT NULL,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ,
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE document_in_document_collection (
    id                      BIGSERIAL PRIMARY KEY,
    document_collection_id  BIGINT  NOT NULL
        CONSTRAINT fk_didc_collection REFERENCES document_collection(id),
    document_id             BIGINT  NOT NULL
        CONSTRAINT fk_didc_document REFERENCES document(id),
    created_by              BIGINT  NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_by              BIGINT,
    deleted_at              TIMESTAMPTZ,
    CONSTRAINT document_in_collection_unique UNIQUE (document_collection_id, document_id)
);

CREATE TABLE user_in_document_collection (
    id                      BIGSERIAL PRIMARY KEY,
    document_collection_id  BIGINT  NOT NULL
        CONSTRAINT fk_uidc_collection REFERENCES document_collection(id),
    user_id                 BIGINT  NOT NULL,
    created_by              BIGINT  NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_by              BIGINT,
    deleted_at              TIMESTAMPTZ,
    CONSTRAINT user_in_collection_unique UNIQUE (document_collection_id, user_id)
);

CREATE INDEX idx_document_chat_id         ON document(chat_id);
CREATE INDEX idx_document_status          ON document(status);
CREATE INDEX idx_document_deleted_at      ON document(deleted_at);

CREATE INDEX idx_fragment_document_id     ON fragment(document_id);
CREATE INDEX idx_fragment_deleted_at      ON fragment(deleted_at);

CREATE INDEX idx_chat_message_chat_id     ON chat_message(chat_id);
CREATE INDEX idx_chat_membership_chat_id  ON chat_membership(chat_id);
CREATE INDEX idx_chat_membership_member   ON chat_membership(member_id);

CREATE INDEX idx_notification_receiver          ON notification(receiver_id);
CREATE INDEX idx_notification_receiver_status   ON notification(receiver_id, status);
CREATE INDEX idx_notification_deleted_at        ON notification(deleted_at);
CREATE INDEX idx_notification_target_scope      ON notification(target_scope);

CREATE TABLE custom_groups (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(150)    NOT NULL UNIQUE,
    description TEXT            NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_by  BIGINT,
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    deleted_by  BIGINT
);

CREATE INDEX custom_gro_name_8c5f90_idx     ON custom_groups(name);
CREATE INDEX custom_gro_deleted_2b06a5_idx  ON custom_groups(deleted_at);

CREATE TABLE documents (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    VARCHAR(255)    NOT NULL,
    description             TEXT            NOT NULL DEFAULT '',
    size_bytes              BIGINT          NOT NULL DEFAULT 0,
    external_document_id    BIGINT          UNIQUE,
    external_storage_url    VARCHAR(1000)   NOT NULL DEFAULT '',
    visible_to_all          BOOLEAN         NOT NULL DEFAULT FALSE,
    minimum_fau_role_id     BIGINT,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_by              BIGINT,
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by              BIGINT,
    deleted_at              TIMESTAMPTZ,
    deleted_by              BIGINT
);

CREATE INDEX documents_name_7e31f9_idx      ON documents(name);
CREATE INDEX documents_deleted_4df53c_idx   ON documents(deleted_at);

CREATE TABLE document_roles (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID            NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    role_id     BIGINT          NOT NULL,
    assigned_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    assigned_by BIGINT,
    CONSTRAINT document_roles_unique UNIQUE (document_id, role_id)
);

CREATE INDEX docrole_doc_50d0b6_idx     ON document_roles(document_id);
CREATE INDEX docrole_role_4a3c85_idx    ON document_roles(role_id);

CREATE TABLE auth_user_custom_groups (
    id              BIGSERIAL   PRIMARY KEY,
    user_id         BIGINT      NOT NULL,
    customgroup_id  UUID        NOT NULL REFERENCES custom_groups(id) ON DELETE CASCADE,
    CONSTRAINT auth_user_custom_groups_unique UNIQUE (user_id, customgroup_id)
);

CREATE TABLE custom_groups_documents (
    id              BIGSERIAL   PRIMARY KEY,
    customgroup_id  UUID        NOT NULL REFERENCES custom_groups(id) ON DELETE CASCADE,
    document_id     UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    CONSTRAINT custom_groups_documents_unique UNIQUE (customgroup_id, document_id)
);

INSERT INTO chat (id, name, created_by)
VALUES (12345, 'Carga administrativa de documentos', 1)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- GRUPOS (áreas institucionales)
-- ============================================
INSERT INTO custom_groups (id, name, description, created_by, created_at) VALUES
    (gen_random_uuid(), 'Contaduría',      'Área de gestión contable y financiera',      1, NOW()),
    (gen_random_uuid(), 'Recursos Humanos','Gestión del personal institucional',          1, NOW()),
    (gen_random_uuid(), 'Operaciones',     'Área de planificación y operaciones aéreas',  1, NOW()),
    (gen_random_uuid(), 'Inteligencia',    'Área de análisis e inteligencia',             1, NOW()),
    (gen_random_uuid(), 'Logística',       'Gestión de recursos y suministros',           1, NOW()),
    (gen_random_uuid(), 'Jurídico',        'Asesoría legal e institucional',              1, NOW()),
    (gen_random_uuid(), 'Comunicaciones',  'Gestión de comunicaciones institucionales',   1, NOW()),
    (gen_random_uuid(), 'Sanidad',         'Área médica y sanitaria',                     1, NOW())
ON CONFLICT (name) DO NOTHING;