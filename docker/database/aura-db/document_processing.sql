CREATE
EXTENSION IF NOT EXISTS vector;
CREATE
EXTENSION IF NOT EXISTS pg_search;
CREATE
EXTENSION IF NOT EXISTS pg_trgm;

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
    enrichment_status      VARCHAR(32)  NOT NULL DEFAULT 'pending'
        CONSTRAINT chk_document_enrichment_status
            CHECK (enrichment_status IN ('pending', 'processed', 'failed', 'not_required')),
    graph_status           VARCHAR(32)  NOT NULL DEFAULT 'pending'
        CONSTRAINT chk_document_graph_status
            CHECK (graph_status IN ('pending', 'processed', 'failed', 'not_required')),
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
    -- Fixed dimension is REQUIRED for an ANN (HNSW) index. 1024 matches every active
    -- embedding model in the .env profiles (HF intfloat/multilingual-e5-large = 1024,
    -- Ollama qwen3-embedding:0.6b = 1024). MUST equal EMBEDDER_VECTOR_DIMENSION / the
    -- active model's output size; changing the embedding model requires recreating
    -- this column and the HNSW index below and re-embedding existing rows.
    vector         VECTOR(1024) NOT NULL,
    -- Provenance of the vector: which embedding model produced it and its dimension.
    -- Recorded per fragment (document.embedder_type is document-level and can drift)
    -- so vectors can be audited and selectively re-embedded when the model changes.
    -- embedding_dim must match the vector column's fixed dimension above.
    embedding_model VARCHAR(255) NOT NULL,
    embedding_dim   INT          NOT NULL DEFAULT 1024
        CONSTRAINT chk_fragment_embedding_dim CHECK (embedding_dim = 1024),
    fragment_index INT         NOT NULL,
    summary        TEXT,
    entities       JSONB,
    topics         TEXT[],
    page_number    INT,
    section_path   TEXT,
    heading        TEXT,
    char_start     INT,
    char_end       INT,
    bbox           JSONB,
    enrichment_status VARCHAR(32) NOT NULL DEFAULT 'pending'
        CONSTRAINT chk_fragment_enrichment_status
            CHECK (enrichment_status IN ('pending', 'processed', 'failed', 'not_required')),
    created_by     BIGINT      NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by     BIGINT,
    updated_at     TIMESTAMPTZ,
    deleted_by     BIGINT,
    deleted_at     TIMESTAMPTZ
);


CREATE INDEX idx_document_status ON document (status);
CREATE INDEX idx_document_enrichment_status ON document (enrichment_status);
CREATE INDEX idx_document_graph_status ON document (graph_status);
CREATE INDEX idx_document_deleted_at ON document (deleted_at);

-- Composite/partial indexes matching the repository's real access patterns. All hot
-- queries filter `deleted_at IS NULL`, so the indexes are partial on the active rows.

-- get_documents_by_chat_id: WHERE chat_id = ? ORDER BY created_at DESC, id DESC.
-- Leftmost `chat_id` also serves plain chat_id equality lookups, so this supersedes the
-- old chat-only index and additionally provides the sort order from the index.
CREATE INDEX idx_document_chat_created_active
    ON document (chat_id, created_at DESC, id DESC) WHERE (deleted_at IS NULL);

-- get_stale_uploaded_documents (outbox reconciliation):
-- WHERE status = 'uploaded' AND created_at <= ? ORDER BY created_at ASC.
CREATE INDEX idx_document_status_created_active
    ON document (status, created_at) WHERE (deleted_at IS NULL);

-- get_documents (global listing/search): WHERE deleted_at IS NULL ORDER BY created_at DESC, id DESC.
CREATE INDEX idx_document_created_active
    ON document (created_at DESC, id DESC) WHERE (deleted_at IS NULL);

-- Trigram GIN indexes for the case-insensitive substring search used by
-- DocumentRepository.get_documents (ILIKE '%term%' on name/description/category).
-- The leading wildcard makes a B-tree index unusable (full table scan); gin_trgm_ops
-- lets PostgreSQL serve the ILIKE/LIKE containment from the index. Partial on the
-- active rows to match the query's `deleted_at IS NULL` filter and keep the index small.
CREATE INDEX idx_document_name_trgm
    ON document USING gin (name gin_trgm_ops) WHERE (deleted_at IS NULL);
CREATE INDEX idx_document_description_trgm
    ON document USING gin (description gin_trgm_ops) WHERE (deleted_at IS NULL);
CREATE INDEX idx_document_category_trgm
    ON document USING gin (category gin_trgm_ops) WHERE (deleted_at IS NULL);

CREATE INDEX idx_fragment_document_id ON fragment (document_id);
CREATE INDEX idx_fragment_deleted_at ON fragment (deleted_at);
CREATE UNIQUE INDEX idx_fragment_doc_index_active
    ON fragment (document_id, fragment_index) WHERE (deleted_at IS NULL);

-- ANN index for semantic search. FragmentRepository.get_most_similar_fragments orders by
-- `vector <=> :query_vector` (cosine distance), so the operator class MUST be
-- vector_cosine_ops to be usable by the planner. Without this index every semantic query
-- is an exact O(N) sequential scan over the whole table.
--
-- Partial on the active rows: all retrieval queries filter `deleted_at IS NULL`, so this
-- keeps soft-deleted fragments out of the graph and shrinks build/search cost.
--
-- Build params: m = max neighbours per node, ef_construction = build-time candidate list.
-- (16 / 64 are pgvector's defaults; raise ef_construction for higher recall at the cost of
-- slower inserts.) Tune query-time recall with `SET hnsw.ef_search = N;` (default 40);
-- raise it when retrieval recall matters more than latency.
CREATE INDEX idx_fragment_vector_hnsw
    ON fragment
    USING hnsw (vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE (deleted_at IS NULL);

CREATE INDEX IF NOT EXISTS fragments_bm25_idx
    ON fragment
    USING bm25 (id, content)
    WITH (key_field = 'id');
