CREATE
EXTENSION IF NOT EXISTS vector;
CREATE
EXTENSION IF NOT EXISTS pg_search;

CREATE TABLE document
(
    id                     BIGSERIAL PRIMARY KEY,
    chat_id                BIGINT
        CONSTRAINT fk_document_chat_id REFERENCES chat (id) ON DELETE CASCADE,
    name                   VARCHAR(255) NOT NULL,
    description            TEXT,
    mime_type              VARCHAR(64)  NOT NULL,
    status                 VARCHAR(64)  NOT NULL DEFAULT 'uploaded'
        CONSTRAINT chk_document_status CHECK (status IN ('uploaded', 'processed', 'failed')),
    storage_url            VARCHAR(255) NOT NULL,
    file_size_bytes        BIGINT       NOT NULL,
    type                   VARCHAR(64),
    category               VARCHAR(255),
    text_cleaner_type      VARCHAR(255),
    text_splitter_type     VARCHAR(255),
    embedder_type          VARCHAR(255),
    split_size             INT,
    split_overlap          INT,
    processing_started_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    processing_finished_at TIMESTAMPTZ,
    created_by             BIGINT       NOT NULL,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by             BIGINT,
    updated_at             TIMESTAMPTZ,
    deleted_by             BIGINT,
    deleted_at             TIMESTAMPTZ
);

CREATE TABLE fragment
(
    id             BIGSERIAL PRIMARY KEY,
    document_id    BIGINT      NOT NULL
        REFERENCES document (id) ON DELETE CASCADE,
    content        TEXT        NOT NULL,
    vector         VECTOR      NOT NULL,
    fragment_index INT         NOT NULL,
    summary        TEXT,
    entities       JSONB,
    topics         TEXT[],
    created_by     BIGINT      NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by     BIGINT,
    updated_at     TIMESTAMPTZ,
    deleted_by     BIGINT,
    deleted_at     TIMESTAMPTZ
);


CREATE INDEX idx_document_status ON document (status);
CREATE INDEX idx_document_deleted_at ON document (deleted_at);
CREATE INDEX idx_document_chat_active ON document (chat_id) WHERE (deleted_at IS NULL);

CREATE INDEX idx_fragment_document_id ON fragment (document_id);
CREATE INDEX idx_fragment_deleted_at ON fragment (deleted_at);
CREATE UNIQUE INDEX idx_fragment_doc_index_active
    ON fragment (document_id, fragment_index) WHERE (deleted_at IS NULL);

CREATE INDEX IF NOT EXISTS fragments_bm25_idx
    ON fragment
    USING bm25 (id, content)
    WITH (key_field = 'id');
