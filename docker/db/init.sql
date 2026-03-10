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
    vector          VECTOR(768)     NOT NULL,
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
    message     VARCHAR(255)        NOT NULL,
    type        notification_type   NOT NULL,
    read_date   TIMESTAMPTZ,
    receiver_id BIGINT              NOT NULL,
    created_by  BIGINT,
    created_at  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
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

CREATE INDEX idx_notification_receiver    ON notification(receiver_id);