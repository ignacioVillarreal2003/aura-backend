CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;

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
    deleted_at  TIMESTAMPTZ,
    tags        TEXT[]                   NOT NULL DEFAULT '{}',
    is_ephemeral BOOLEAN                NOT NULL DEFAULT FALSE,
    is_locked   BOOLEAN                 NOT NULL DEFAULT FALSE
);

CREATE TABLE document (
    id                      BIGSERIAL PRIMARY KEY,
    chat_id                 BIGINT
        CONSTRAINT fk_document_chat_id REFERENCES chat(id) ON DELETE CASCADE,
    name                    VARCHAR(255)    NOT NULL,
    description             TEXT,
    mime_type               VARCHAR(64)         NOT NULL,
    status                  VARCHAR(64)         NOT NULL DEFAULT 'uploaded',
    storage_url             VARCHAR(255)    NOT NULL,
    file_size_bytes         BIGINT          NOT NULL,
    type                    VARCHAR(64),
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
    sender_type VARCHAR(64)                   NOT NULL,
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
    status      VARCHAR(64)               NOT NULL,
    joined_at   TIMESTAMPTZ,
    left_at     TIMESTAMPTZ,
    created_by  BIGINT                  NOT NULL,
    created_at  TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ,
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    pinned_at   TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    last_read_at TIMESTAMPTZ,
    role        VARCHAR(64)             NOT NULL DEFAULT 'editor',
    muted_until TIMESTAMPTZ
);

CREATE TABLE pinned_message (
    id          BIGSERIAL PRIMARY KEY,
    message_id  BIGINT                  NOT NULL,
    chat_id     BIGINT                  NOT NULL,
    pinned_by   BIGINT                  NOT NULL,
    pinned_at   TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    CONSTRAINT pinned_message_unique UNIQUE (message_id, chat_id),
    CONSTRAINT fk_pinned_message_message FOREIGN KEY (message_id) REFERENCES chat_message(id) ON DELETE CASCADE,
    CONSTRAINT fk_pinned_message_chat FOREIGN KEY (chat_id) REFERENCES chat(id) ON DELETE CASCADE
);

CREATE TABLE message_bookmark (
    id          BIGSERIAL PRIMARY KEY,
    message_id  BIGINT                  NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
    user_id     BIGINT                  NOT NULL,
    created_at  TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_message_bookmark UNIQUE (message_id, user_id)
);

CREATE TABLE message_thread_reply (
    id                  BIGSERIAL PRIMARY KEY,
    parent_message_id   BIGINT                  NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
    message             TEXT                  NOT NULL,
    created_by          BIGINT                NOT NULL,
    created_at          TIMESTAMPTZ           NOT NULL DEFAULT NOW()
);

CREATE TABLE message_feedback (
    id          BIGSERIAL PRIMARY KEY,
    message_id  BIGINT                  NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
    user_id     BIGINT                  NOT NULL,
    value       SMALLINT                NOT NULL,
    created_at  TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ,
    CONSTRAINT uq_message_feedback UNIQUE (message_id, user_id),
    CONSTRAINT chk_feedback_value CHECK (value IN (1, -1))
);

CREATE TABLE chat_share_link (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT                  NOT NULL REFERENCES chat(id) ON DELETE CASCADE,
    token       UUID                    NOT NULL DEFAULT gen_random_uuid(),
    created_by  BIGINT                  NOT NULL,
    created_at  TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ,
    is_active   BOOLEAN                 NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_share_link_token UNIQUE (token)
);

CREATE TABLE chat_webhook (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT                  NOT NULL,
    url         TEXT                    NOT NULL,
    events      TEXT[]                  NOT NULL DEFAULT '{}',
    secret      VARCHAR(64)             NOT NULL,
    is_active   BOOLEAN                 NOT NULL DEFAULT TRUE,
    created_by  BIGINT                  NOT NULL,
    created_at  TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_chat_webhook_chat FOREIGN KEY (chat_id) REFERENCES chat(id) ON DELETE CASCADE
);

CREATE TABLE notification (
    id          BIGSERIAL PRIMARY KEY,
    receiver_id BIGINT              NOT NULL,
    message     VARCHAR(500)        NOT NULL,
    type        VARCHAR(64)         NOT NULL DEFAULT 'system',
    target_scope VARCHAR(64)        NOT NULL DEFAULT 'individual',
    target_label VARCHAR(255),
    status      VARCHAR(64)         NOT NULL DEFAULT 'unread',
    read_at     TIMESTAMPTZ,
    created_by  BIGINT,
    created_at  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ,
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    event_type  VARCHAR(128),
    event_key   VARCHAR(128),
    data        JSONB               NOT NULL DEFAULT '{}'::jsonb,
    link_url    TEXT,
    severity    VARCHAR(16)         NOT NULL DEFAULT 'info',
    sender_name VARCHAR(255)
);

CREATE TABLE notification_preference (
    user_id           BIGINT       PRIMARY KEY,
    inapp_enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    email_enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    mute_until        TIMESTAMPTZ,
    quiet_hours_start TIME,
    quiet_hours_end   TIME,
    quiet_hours_tz    VARCHAR(64)  NOT NULL DEFAULT 'UTC',
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ,
    updated_by        BIGINT
);

CREATE TABLE notification_event_preference (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT       NOT NULL,
    event_type  VARCHAR(128) NOT NULL,
    channel     VARCHAR(16)  NOT NULL,
    enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ,
    CONSTRAINT  notification_event_preference_channel_chk
        CHECK (channel IN ('inapp', 'email')),
    CONSTRAINT  notification_event_preference_unique
        UNIQUE (user_id, event_type, channel)
);

CREATE TABLE notification_dispatch (
    id              BIGSERIAL    PRIMARY KEY,
    notification_id BIGINT       REFERENCES notification(id) ON DELETE SET NULL,
    receiver_id     BIGINT       NOT NULL,
    event_type      VARCHAR(128) NOT NULL,
    channel         VARCHAR(16)  NOT NULL,
    status          VARCHAR(16)  NOT NULL DEFAULT 'pending',
    attempt         INT          NOT NULL DEFAULT 0,
    error           TEXT,
    metadata        JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    sent_at         TIMESTAMPTZ,
    CONSTRAINT      notification_dispatch_channel_chk
        CHECK (channel IN ('inapp', 'email', 'webpush', 'sms')),
    CONSTRAINT      notification_dispatch_status_chk
        CHECK (status IN ('pending', 'sent', 'failed', 'skipped', 'suppressed'))
);

CREATE TABLE classification_level (
    id      BIGSERIAL PRIMARY KEY,
    name    VARCHAR(100) NOT NULL UNIQUE,
    rank    SMALLINT NOT NULL UNIQUE CHECK (rank >= 0)
);

CREATE TABLE compartment (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100)    NOT NULL UNIQUE,
    description TEXT            NOT NULL DEFAULT ''
);

CREATE TABLE document_collection (
    id                       BIGSERIAL PRIMARY KEY,
    name                     VARCHAR(255)    NOT NULL,
    classification_level_id  BIGINT
        REFERENCES classification_level(id),
    created_by               BIGINT          NOT NULL,
    created_at               TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by               BIGINT,
    updated_at               TIMESTAMPTZ,
    deleted_by               BIGINT,
    deleted_at               TIMESTAMPTZ
);

CREATE TABLE document_collection_compartment (
    id                      BIGSERIAL PRIMARY KEY,
    document_collection_id  BIGINT NOT NULL
        CONSTRAINT fk_doc_coll_comp_collection REFERENCES document_collection(id),
    compartment_id          BIGINT NOT NULL
        CONSTRAINT fk_doc_coll_comp_compartment REFERENCES compartment(id),
    created_by              BIGINT          NOT NULL,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT doc_coll_comp_coll_compartment_unique UNIQUE (document_collection_id, compartment_id)
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
    deleted_at              TIMESTAMPTZ
);

CREATE TABLE user_clearance (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT NOT NULL UNIQUE,
    classification_level_id BIGINT NOT NULL
        REFERENCES classification_level(id),
    created_by              BIGINT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_compartment (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL,
    compartment_id   BIGINT NOT NULL
        REFERENCES compartment(id),
    created_by       BIGINT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT user_compartment_user_compartment_unique UNIQUE (user_id, compartment_id)
);

CREATE INDEX idx_document_status          ON document(status);
CREATE INDEX idx_document_deleted_at      ON document(deleted_at);
CREATE INDEX idx_document_chat_active        ON document(chat_id) WHERE (deleted_at IS NULL);

CREATE INDEX idx_fragment_document_id     ON fragment(document_id);
CREATE INDEX idx_fragment_deleted_at      ON fragment(deleted_at);
CREATE UNIQUE INDEX idx_fragment_doc_index_active
    ON fragment (document_id, fragment_index) WHERE (deleted_at IS NULL);

CREATE INDEX IF NOT EXISTS fragments_bm25_idx
    ON fragment
    USING bm25 (id, content)
    WITH (key_field = 'id');

CREATE INDEX idx_chat_message_chat_created_active
    ON chat_message (chat_id, created_at) WHERE (deleted_at IS NULL);
CREATE INDEX idx_chat_message_chat_created
    ON chat_message (chat_id, created_at DESC);
CREATE INDEX idx_chat_message_chat_id ON chat_message(chat_id);
CREATE INDEX idx_chat_message_deleted_at ON chat_message(deleted_at);
CREATE INDEX idx_chat_created_by_active     ON chat (created_by) WHERE (deleted_at IS NULL);
CREATE INDEX idx_chat_deleted_at            ON chat(deleted_at);

CREATE UNIQUE INDEX chat_membership_member_chat_unique
    ON chat_membership (member_id, chat_id)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_chat_membership_chat_member_status
    ON chat_membership (chat_id, member_id, status);
CREATE INDEX idx_chat_membership_chat_id  ON chat_membership(chat_id);
CREATE INDEX idx_chat_membership_member   ON chat_membership(member_id);
CREATE INDEX idx_chat_membership_deleted_at ON chat_membership(deleted_at);

CREATE INDEX idx_pinned_message_chat ON pinned_message(chat_id);
CREATE INDEX idx_pinned_message_message ON pinned_message(message_id);
CREATE INDEX idx_message_bookmark_message ON message_bookmark(message_id);
CREATE INDEX idx_message_bookmark_user ON message_bookmark(user_id);
CREATE INDEX idx_thread_reply_parent ON message_thread_reply(parent_message_id);
CREATE INDEX idx_message_feedback_message ON message_feedback(message_id);
CREATE INDEX idx_share_link_chat ON chat_share_link(chat_id);
CREATE INDEX idx_share_link_token ON chat_share_link(token);
CREATE INDEX idx_chat_webhook_chat ON chat_webhook(chat_id);

CREATE INDEX idx_notification_deleted_at        ON notification(deleted_at);
CREATE INDEX idx_notification_target_scope      ON notification(target_scope);

CREATE INDEX notif_receiver_status_created_idx
    ON notification (receiver_id, status, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX notif_receiver_event_type_created_idx
    ON notification (receiver_id, event_type, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX notif_receiver_event_key_active_uq
    ON notification (receiver_id, event_key)
    WHERE event_key IS NOT NULL AND deleted_at IS NULL;

CREATE INDEX notif_severity_idx
    ON notification (severity)
    WHERE deleted_at IS NULL;

CREATE INDEX notification_preference_mute_until_idx
    ON notification_preference (mute_until)
    WHERE mute_until IS NOT NULL;

CREATE INDEX notification_event_preference_user_idx
    ON notification_event_preference (user_id);

CREATE INDEX notification_dispatch_notification_idx
    ON notification_dispatch (notification_id);

CREATE INDEX notification_dispatch_receiver_created_idx
    ON notification_dispatch (receiver_id, created_at DESC);

CREATE INDEX notification_dispatch_status_idx
    ON notification_dispatch (status, created_at DESC);

CREATE INDEX notification_dispatch_event_type_idx
    ON notification_dispatch (event_type, created_at DESC);

CREATE UNIQUE INDEX idx_document_in_collection_active_unique
    ON document_in_document_collection (document_collection_id, document_id)
    WHERE deleted_at IS NULL;

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
