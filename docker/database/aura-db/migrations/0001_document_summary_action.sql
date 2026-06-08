-- Migration: add artifact_document_summary and artifact_document_action tables
-- Run against an existing aura-db instance (init.sql already includes these for fresh volumes).

-- Update artifact type CHECK constraint to include new types
ALTER TABLE artifact DROP CONSTRAINT IF EXISTS chk_artifact_type;
ALTER TABLE artifact ADD CONSTRAINT chk_artifact_type CHECK (type IN (
    'MESSAGE', 'REPORT', 'CHECKLIST', 'QUIZ',
    'TIMELINE', 'LESSONS_LEARNED', 'DECISION_BRIEF',
    'DOCUMENT_SUMMARY', 'DOCUMENT_ACTION'
));

-- ============================================================================
-- artifact_document_summary  (type = DOCUMENT_SUMMARY)
-- ============================================================================
CREATE TABLE IF NOT EXISTS artifact_document_summary (
    id           BIGSERIAL PRIMARY KEY,
    artifact_id  BIGINT          NOT NULL
        CONSTRAINT fk_artifact_document_summary_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    document_ids JSONB           NOT NULL DEFAULT '[]'::jsonb,
    summary      TEXT            NOT NULL DEFAULT '',
    created_by   BIGINT          NOT NULL,
    created_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by   BIGINT,
    updated_at   TIMESTAMPTZ,
    deleted_by   BIGINT,
    deleted_at   TIMESTAMPTZ,
    CONSTRAINT uq_artifact_document_summary_artifact UNIQUE (artifact_id)
);

CREATE INDEX IF NOT EXISTS idx_artifact_document_summary_artifact ON artifact_document_summary (artifact_id);
CREATE INDEX IF NOT EXISTS idx_artifact_document_summary_owner    ON artifact_document_summary (created_by, created_at DESC) WHERE deleted_at IS NULL;

-- ============================================================================
-- artifact_document_action  (type = DOCUMENT_ACTION)
-- ============================================================================
CREATE TABLE IF NOT EXISTS artifact_document_action (
    id           BIGSERIAL PRIMARY KEY,
    artifact_id  BIGINT          NOT NULL
        CONSTRAINT fk_artifact_document_action_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    document_ids JSONB           NOT NULL DEFAULT '[]'::jsonb,
    instruction  TEXT            NOT NULL DEFAULT '',
    action       VARCHAR(32),
    result       TEXT            NOT NULL DEFAULT '',
    created_by   BIGINT          NOT NULL,
    created_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by   BIGINT,
    updated_at   TIMESTAMPTZ,
    deleted_by   BIGINT,
    deleted_at   TIMESTAMPTZ,
    CONSTRAINT uq_artifact_document_action_artifact UNIQUE (artifact_id)
);

CREATE INDEX IF NOT EXISTS idx_artifact_document_action_artifact ON artifact_document_action (artifact_id);
CREATE INDEX IF NOT EXISTS idx_artifact_document_action_owner    ON artifact_document_action (created_by, created_at DESC) WHERE deleted_at IS NULL;
