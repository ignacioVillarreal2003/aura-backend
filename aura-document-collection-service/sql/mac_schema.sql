-- =============================================================
-- MAC (Mandatory Access Control) schema
-- Run in order — each block depends on the previous ones.
-- =============================================================

-- -------------------------------------------------------------
-- 1. classification_level
--    Vertical axis: ordered security levels (rank is ordinal).
-- -------------------------------------------------------------
CREATE TABLE classification_level (
    id   BIGSERIAL    PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    rank SMALLINT     NOT NULL CHECK (rank >= 1),
    CONSTRAINT uq_classification_level_name UNIQUE (name),
    CONSTRAINT uq_classification_level_rank UNIQUE (rank)
);

-- -------------------------------------------------------------
-- 2. compartment
--    Horizontal axis: independent area/department labels.
-- -------------------------------------------------------------
CREATE TABLE compartment (
    id          BIGSERIAL    PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    description TEXT         NOT NULL DEFAULT '',
    CONSTRAINT uq_compartment_name UNIQUE (name)
);

-- -------------------------------------------------------------
-- 3. Alter document_collection
--    Add classification_level FK (nullable for existing rows).
-- -------------------------------------------------------------
ALTER TABLE document_collection
    ADD COLUMN classification_level_id BIGINT
        REFERENCES classification_level (id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE;

CREATE INDEX idx_document_collection_classification_level
    ON document_collection (classification_level_id)
    WHERE classification_level_id IS NOT NULL;

-- -------------------------------------------------------------
-- 4. document_collection_compartment
--    M2M between collections and compartments.
-- -------------------------------------------------------------
CREATE TABLE document_collection_compartment (
    id                       BIGSERIAL NOT NULL PRIMARY KEY,
    document_collection_id   BIGINT    NOT NULL
        REFERENCES document_collection (id)
        ON DELETE CASCADE,
    compartment_id           BIGINT    NOT NULL
        REFERENCES compartment (id)
        ON DELETE RESTRICT,
    created_by               BIGINT    NOT NULL,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_collection_compartment
        UNIQUE (document_collection_id, compartment_id)
);

CREATE INDEX idx_dcc_document_collection_id
    ON document_collection_compartment (document_collection_id);
CREATE INDEX idx_dcc_compartment_id
    ON document_collection_compartment (compartment_id);

-- -------------------------------------------------------------
-- 5. user_clearance
--    One clearance level per user (upsert-managed by the app).
-- -------------------------------------------------------------
CREATE TABLE user_clearance (
    id                      BIGSERIAL   PRIMARY KEY,
    user_id                 BIGINT      NOT NULL,
    classification_level_id BIGINT      NOT NULL
        REFERENCES classification_level (id)
        ON DELETE RESTRICT,
    created_by              BIGINT      NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_clearance_user_id UNIQUE (user_id)
);

CREATE INDEX idx_user_clearance_classification_level
    ON user_clearance (classification_level_id);

-- -------------------------------------------------------------
-- 6. user_compartment
--    M2M between users and compartments.
-- -------------------------------------------------------------
CREATE TABLE user_compartment (
    id             BIGSERIAL   PRIMARY KEY,
    user_id        BIGINT      NOT NULL,
    compartment_id BIGINT      NOT NULL
        REFERENCES compartment (id)
        ON DELETE RESTRICT,
    created_by     BIGINT      NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_compartment UNIQUE (user_id, compartment_id)
);

CREATE INDEX idx_user_compartment_user_id
    ON user_compartment (user_id);
CREATE INDEX idx_user_compartment_compartment_id
    ON user_compartment (compartment_id);

-- -------------------------------------------------------------
-- 7. Drop the old user_in_document_collection table.
--    Run this only after confirming no other service depends on it.
-- -------------------------------------------------------------
DROP TABLE IF EXISTS user_in_document_collection;
