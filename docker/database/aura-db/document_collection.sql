CREATE TABLE classification_level
(
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    rank        SMALLINT     NOT NULL UNIQUE CHECK (rank >= 0),
    description TEXT         NOT NULL DEFAULT ''
);

CREATE TABLE compartment
(
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT         NOT NULL DEFAULT ''
);

CREATE TABLE document_collection
(
    id                      BIGSERIAL PRIMARY KEY,
    name                    VARCHAR(255) NOT NULL,
    classification_level_id BIGINT
        REFERENCES classification_level (id),
    created_by              BIGINT       NOT NULL,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by              BIGINT,
    updated_at              TIMESTAMPTZ,
    deleted_by              BIGINT,
    deleted_at              TIMESTAMPTZ
);

CREATE TABLE document_collection_compartment
(
    id                     BIGSERIAL PRIMARY KEY,
    document_collection_id BIGINT      NOT NULL
        CONSTRAINT fk_doc_coll_comp_collection REFERENCES document_collection (id),
    compartment_id         BIGINT      NOT NULL
        CONSTRAINT fk_doc_coll_comp_compartment REFERENCES compartment (id),
    created_by             BIGINT      NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT doc_coll_comp_coll_compartment_unique UNIQUE (document_collection_id, compartment_id)
);

CREATE TABLE document_in_document_collection
(
    id                     BIGSERIAL PRIMARY KEY,
    document_collection_id BIGINT      NOT NULL
        CONSTRAINT fk_didc_collection REFERENCES document_collection (id),
    document_id            BIGINT      NOT NULL
        CONSTRAINT fk_didc_document REFERENCES document (id),
    created_by             BIGINT      NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_by             BIGINT,
    deleted_at             TIMESTAMPTZ
);

CREATE TABLE user_clearance
(
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT      NOT NULL UNIQUE,
    classification_level_id BIGINT      NOT NULL
        REFERENCES classification_level (id),
    created_by              BIGINT      NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_compartment
(
    id             BIGSERIAL PRIMARY KEY,
    user_id        BIGINT      NOT NULL,
    compartment_id BIGINT      NOT NULL
        REFERENCES compartment (id),
    created_by     BIGINT      NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT user_compartment_user_compartment_unique UNIQUE (user_id, compartment_id)
);


CREATE UNIQUE INDEX idx_document_in_collection_active_unique
    ON document_in_document_collection (document_collection_id, document_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_document_collection_classification_level_id
    ON document_collection (classification_level_id);
CREATE INDEX idx_document_collection_deleted_at
    ON document_collection (deleted_at);
CREATE INDEX idx_document_collection_compartment_collection
    ON document_collection_compartment (document_collection_id);
CREATE INDEX idx_document_collection_compartment_compartment
    ON document_collection_compartment (compartment_id);
CREATE INDEX idx_user_clearance_classification_level_id
    ON user_clearance (classification_level_id);
CREATE INDEX idx_user_compartment_user_id
    ON user_compartment (user_id);
CREATE INDEX idx_user_compartment_compartment_id
    ON user_compartment (compartment_id);


INSERT INTO classification_level (name, rank)
VALUES ('PUBLIC', 1),
       ('INTERNAL', 2),
       ('CONFIDENTIAL', 3),
       ('RESTRICTED', 4);

INSERT INTO compartment (name, description)
VALUES ('Program-Alpha', 'Necesidad de conocer programa Alpha (manual operativo general).'),
       ('Program-Bravo', 'Ámbito Bravo (información táctica de unidad).'),
       ('Program-Charlie', 'Integración sistemas Charlie (solo personal asignado).');
