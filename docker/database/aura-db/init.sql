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

CREATE TYPE notification_status AS ENUM (
    'unread',
    'read',
    'archived'
);

CREATE TYPE notification_target_scope AS ENUM (
    'individual',
    'group',
    'system'
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
    type         notification_type          NOT NULL,
    target_scope notification_target_scope  NOT NULL DEFAULT 'individual',
    target_label VARCHAR(255),
    status       notification_status        NOT NULL DEFAULT 'unread',
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

CREATE INDEX idx_document_status          ON document(status);
CREATE INDEX idx_document_deleted_at      ON document(deleted_at);
CREATE INDEX idx_document_chat_active        ON document(chat_id) WHERE (deleted_at IS NULL);

CREATE INDEX idx_fragment_document_id     ON fragment(document_id);
CREATE INDEX idx_fragment_deleted_at      ON fragment(deleted_at);
CREATE UNIQUE INDEX idx_fragment_doc_index_active
    ON fragment (document_id, fragment_index) WHERE (deleted_at IS NULL);
CREATE INDEX idx_fragment_vector_hnsw
    ON fragment USING hnsw (vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE (deleted_at IS NULL);

CREATE INDEX idx_chat_message_chat_created_active
    ON chat_message (chat_id, created_at) WHERE (deleted_at IS NULL);
CREATE INDEX idx_chat_created_by_active     ON chat (created_by) WHERE (deleted_at IS NULL);

CREATE INDEX idx_chat_membership_chat_id  ON chat_membership(chat_id);
CREATE INDEX idx_chat_membership_member   ON chat_membership(member_id);

CREATE INDEX idx_notification_receiver_status   ON notification(receiver_id, status);
CREATE INDEX idx_notification_receiver_created   ON notification(receiver_id, created_at DESC);
CREATE INDEX idx_notification_deleted_at        ON notification(deleted_at);
CREATE INDEX idx_notification_target_scope      ON notification(target_scope);

INSERT INTO chat (name, system_prompt, response_style, last_message_at, created_by)
VALUES
    (
        'Análisis — Reglamento interno Alpha',
        'Respondé de forma técnica y breve, basándote solo en el contexto aportado.',
        'conciso',
        NOW() - INTERVAL '2 hours',
        4
    ),
    (
        'Consultas — Doctrina unidad Bravo',
        'Usá español formal; cuando cites normativa, indicá el apartado si lo conocés.',
        'formal',
        NOW() - INTERVAL '1 day',
        5
    );

INSERT INTO chat_membership (member_id, chat_id, status, joined_at, left_at, created_by)
VALUES
    (4, 1, 'active',   NOW() - INTERVAL '8 days',  NULL, 4),
    (5, 1, 'active',   NOW() - INTERVAL '7 days',  NULL, 4),
    (4, 2, 'active',   NOW() - INTERVAL '6 days',  NULL, 5),
    (5, 2, 'active',   NOW() - INTERVAL '5 days',  NULL, 5),
    (6, 2, 'pending',  NULL,                      NULL, 5);

INSERT INTO document_collection (name, created_by)
VALUES
    ('Colección — Manuales de vuelo (2024)',       4),
    ('Colección — Informes tácticos equipo sur',  6);

INSERT INTO user_in_document_collection (document_collection_id, user_id, created_by)
VALUES
    (1, 4, 4),
    (1, 5, 4),
    (2, 5, 6),
    (2, 6, 6),
    (2, 4, 6);
