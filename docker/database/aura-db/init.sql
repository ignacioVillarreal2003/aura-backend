CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;

-- ============================================================================
-- chat
-- ============================================================================
CREATE TABLE chat (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(255)             NOT NULL,
    system_prompt       TEXT,
    response_style      TEXT,
    last_message_at     TIMESTAMPTZ,
    source_assistant_id BIGINT,
    created_by          BIGINT                   NOT NULL,
    created_at          TIMESTAMPTZ              NOT NULL DEFAULT NOW(),
    updated_by          BIGINT,
    updated_at          TIMESTAMPTZ,
    deleted_by          BIGINT,
    deleted_at          TIMESTAMPTZ,
    tags                TEXT[]                   NOT NULL DEFAULT '{}',
    is_ephemeral        BOOLEAN                  NOT NULL DEFAULT FALSE,
    is_locked           BOOLEAN                  NOT NULL DEFAULT FALSE
);

-- ============================================================================
-- document / fragment
-- ============================================================================
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

-- ============================================================================
-- chat_membership
-- ============================================================================
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

-- ============================================================================
-- chat_share_link
-- ============================================================================
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

-- ============================================================================
-- notification
-- ============================================================================
CREATE TABLE notification (
    id              BIGSERIAL PRIMARY KEY,
    receiver_id     BIGINT        NOT NULL,
    message         VARCHAR(500)  NOT NULL,
    type            VARCHAR(64)   NOT NULL DEFAULT 'system',
    event_type      VARCHAR(128),
    event_key       VARCHAR(128),
    data            JSONB         NOT NULL DEFAULT '{}'::jsonb,
    target_scope    VARCHAR(64)   NOT NULL DEFAULT 'individual',
    target_label    VARCHAR(255),
    sender_name     VARCHAR(255),
    severity        VARCHAR(16)   NOT NULL DEFAULT 'info',
    title           VARCHAR(150),
    link_url        VARCHAR(2048),
    status          VARCHAR(64)   NOT NULL DEFAULT 'unread',
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    created_by      BIGINT,
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_by      BIGINT,
    deleted_at      TIMESTAMPTZ,
    deleted_by      BIGINT
);

CREATE TABLE notification_dispatch (
    id              BIGSERIAL PRIMARY KEY,
    notification_id BIGINT,
    receiver_id     BIGINT        NOT NULL,
    event_type      VARCHAR(128)  NOT NULL,
    channel         VARCHAR(16)   NOT NULL,
    status          VARCHAR(16)   NOT NULL DEFAULT 'pending',
    attempt         INTEGER       NOT NULL DEFAULT 0,
    error           TEXT,
    metadata        JSONB         NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    sent_at         TIMESTAMPTZ,
    CONSTRAINT notification_dispatch_notification_id_fkey
        FOREIGN KEY (notification_id) REFERENCES notification(id) ON DELETE SET NULL,
    CONSTRAINT notification_dispatch_channel_chk
        CHECK (channel IN ('inapp', 'email', 'webpush', 'sms')),
    CONSTRAINT notification_dispatch_status_chk
        CHECK (status IN ('pending', 'sent', 'failed', 'skipped', 'suppressed'))
);

CREATE TABLE notification_preference (
    user_id             BIGINT PRIMARY KEY,
    inapp_enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    email_enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    mute_until          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by          BIGINT,
    updated_at          TIMESTAMPTZ,
    updated_by          BIGINT
);

CREATE TABLE notification_event_preference (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT       NOT NULL,
    event_type  VARCHAR(128) NOT NULL,
    channel     VARCHAR(16)  NOT NULL,
    enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ,
    updated_by  BIGINT,
    UNIQUE (user_id, event_type, channel),
    CONSTRAINT notification_event_preference_channel_chk
        CHECK (channel IN ('inapp', 'email'))
);

-- ============================================================================
-- classification / compartment / collection / clearance
-- ============================================================================
CREATE TABLE classification_level (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    rank        SMALLINT NOT NULL UNIQUE CHECK (rank >= 0),
    description TEXT NOT NULL DEFAULT ''
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

-- ============================================================================
-- assistant
-- ============================================================================
CREATE TABLE assistant (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(256)    NOT NULL,
    description     TEXT            NOT NULL DEFAULT '',
    system_prompt   TEXT            NOT NULL,
    response_style  TEXT            NOT NULL DEFAULT '',
    avatar_emoji    VARCHAR(16)     NOT NULL DEFAULT '',
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_by      BIGINT          NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by      BIGINT,
    updated_at      TIMESTAMPTZ,
    deleted_by      BIGINT,
    deleted_at      TIMESTAMPTZ
);

ALTER TABLE chat
    ADD CONSTRAINT fk_chat_source_assistant
    FOREIGN KEY (source_assistant_id) REFERENCES assistant(id) ON DELETE SET NULL;

-- ============================================================================
-- artifact  (unified header — every chat item is an artifact)
-- ============================================================================
CREATE TABLE artifact (
    id              BIGSERIAL PRIMARY KEY,
    type            VARCHAR(32)     NOT NULL
        CONSTRAINT chk_artifact_type CHECK (type IN (
            'MESSAGE', 'REPORT', 'CHECKLIST', 'QUIZ',
            'TIMELINE', 'LESSONS_LEARNED', 'DECISION_BRIEF'
        )),
    title           VARCHAR(500)    NOT NULL DEFAULT '',
    description     TEXT            NOT NULL DEFAULT '',
    status          VARCHAR(16)     NOT NULL DEFAULT 'draft'
        CONSTRAINT chk_artifact_status CHECK (status IN ('draft', 'final', 'archived')),
    version         INT             NOT NULL DEFAULT 1,
    mode            VARCHAR(16)     NOT NULL DEFAULT 'direct'
        CONSTRAINT chk_artifact_mode CHECK (mode IN ('direct', 'rag')),
    fragments       JSONB,
    source_chat_id  BIGINT          NOT NULL
        CONSTRAINT fk_artifact_source_chat REFERENCES chat(id) ON DELETE CASCADE,
    created_by      BIGINT          NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by      BIGINT,
    updated_at      TIMESTAMPTZ,
    deleted_by      BIGINT,
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE artifact_version (
    id              BIGSERIAL PRIMARY KEY,
    artifact_id     BIGINT          NOT NULL
        CONSTRAINT fk_artifact_version_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    version_number  INT             NOT NULL,
    title           VARCHAR(500)    NOT NULL,
    description     TEXT            NOT NULL DEFAULT '',
    status          VARCHAR(16)     NOT NULL,
    mode            VARCHAR(16)     NOT NULL DEFAULT 'direct',
    change_summary  TEXT            NOT NULL DEFAULT '',
    created_by      BIGINT          NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_artifact_version UNIQUE (artifact_id, version_number)
);

-- ============================================================================
-- artifact_message  (type = MESSAGE)
-- ============================================================================
CREATE TABLE artifact_message (
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT          NOT NULL
        CONSTRAINT fk_artifact_message_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    message     TEXT            NOT NULL,
    sender_type VARCHAR(16)     NOT NULL
        CONSTRAINT chk_artifact_message_sender CHECK (sender_type IN ('user', 'assistant', 'system')),
    created_by  BIGINT,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_message_artifact UNIQUE (artifact_id)
);

-- ============================================================================
-- artifact_pin / artifact_bookmark / artifact_thread_reply / artifact_feedback
-- ============================================================================
CREATE TABLE artifact_pin (
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT          NOT NULL
        CONSTRAINT fk_artifact_pin_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    chat_id     BIGINT          NOT NULL
        CONSTRAINT fk_artifact_pin_chat REFERENCES chat(id) ON DELETE CASCADE,
    pinned_by   BIGINT          NOT NULL,
    pinned_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT artifact_pin_unique UNIQUE (artifact_id, chat_id)
);

CREATE TABLE artifact_bookmark (
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT          NOT NULL
        CONSTRAINT fk_artifact_bookmark_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    user_id     BIGINT          NOT NULL,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_artifact_bookmark UNIQUE (artifact_id, user_id)
);

CREATE TABLE artifact_thread_reply (
    id                  BIGSERIAL PRIMARY KEY,
    parent_artifact_id  BIGINT          NOT NULL
        CONSTRAINT fk_artifact_thread_reply_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    message             TEXT            NOT NULL,
    created_by          BIGINT          NOT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE artifact_feedback (
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT          NOT NULL
        CONSTRAINT fk_artifact_feedback_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    user_id     BIGINT          NOT NULL,
    value       SMALLINT        NOT NULL,
    reason      VARCHAR(32),
    comment     VARCHAR(500),
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_feedback UNIQUE (artifact_id, user_id),
    CONSTRAINT chk_artifact_feedback_value CHECK (value IN (1, -1)),
    CONSTRAINT chk_artifact_feedback_reason CHECK (
        reason IS NULL OR reason IN (
            'incorrect', 'incomplete', 'off_topic', 'tone', 'too_long', 'hallucination', 'other'
        )
    )
);

-- ============================================================================
-- artifact_report  (type = REPORT)
-- ============================================================================
CREATE TABLE artifact_report (
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT          NOT NULL
        CONSTRAINT fk_artifact_report_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    type        VARCHAR(16)     NOT NULL
        CONSTRAINT chk_artifact_report_type CHECK (type IN ('SITREP', 'INTSUM', 'OPORD')),
    content     TEXT            NOT NULL,
    created_by  BIGINT          NOT NULL,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ,
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_report_artifact UNIQUE (artifact_id)
);

-- ============================================================================
-- artifact_checklist  (type = CHECKLIST)
-- ============================================================================
CREATE TABLE artifact_checklist (
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT          NOT NULL
        CONSTRAINT fk_artifact_checklist_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    created_by  BIGINT          NOT NULL,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ,
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_checklist_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_checklist_section (
    id           BIGSERIAL PRIMARY KEY,
    checklist_id BIGINT       NOT NULL
        CONSTRAINT fk_artifact_checklist_section_checklist REFERENCES artifact_checklist(id) ON DELETE CASCADE,
    title        VARCHAR(200) NOT NULL,
    position     SMALLINT     NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE artifact_checklist_item (
    id         BIGSERIAL PRIMARY KEY,
    section_id BIGINT       NOT NULL
        CONSTRAINT fk_artifact_checklist_item_section REFERENCES artifact_checklist_section(id) ON DELETE CASCADE,
    text       VARCHAR(500) NOT NULL,
    is_checked BOOLEAN      NOT NULL DEFAULT FALSE,
    notes      TEXT         NOT NULL DEFAULT '',
    position   SMALLINT     NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- ============================================================================
-- artifact_quiz  (type = QUIZ)
-- ============================================================================
CREATE TABLE artifact_quiz (
    id           BIGSERIAL PRIMARY KEY,
    artifact_id  BIGINT          NOT NULL
        CONSTRAINT fk_artifact_quiz_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    instructions TEXT            NOT NULL DEFAULT '',
    pass_score   SMALLINT,
    created_by   BIGINT          NOT NULL,
    created_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by   BIGINT,
    updated_at   TIMESTAMPTZ,
    deleted_by   BIGINT,
    deleted_at   TIMESTAMPTZ,
    CONSTRAINT uq_artifact_quiz_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_quiz_question (
    id          BIGSERIAL PRIMARY KEY,
    quiz_id     BIGINT          NOT NULL
        CONSTRAINT fk_artifact_quiz_question_quiz REFERENCES artifact_quiz(id) ON DELETE CASCADE,
    text        TEXT            NOT NULL,
    kind        VARCHAR(16)     NOT NULL DEFAULT 'single'
        CONSTRAINT chk_artifact_quiz_question_kind CHECK (kind IN ('single', 'multiple', 'boolean', 'open')),
    explanation TEXT            NOT NULL DEFAULT '',
    position    SMALLINT        NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE artifact_quiz_option (
    id          BIGSERIAL PRIMARY KEY,
    question_id BIGINT          NOT NULL
        CONSTRAINT fk_artifact_quiz_option_question REFERENCES artifact_quiz_question(id) ON DELETE CASCADE,
    text        VARCHAR(500)    NOT NULL,
    is_correct  BOOLEAN         NOT NULL DEFAULT FALSE,
    position    SMALLINT        NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- artifact_timeline  (type = TIMELINE)
-- ============================================================================
CREATE TABLE artifact_timeline (
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT          NOT NULL
        CONSTRAINT fk_artifact_timeline_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    summary     TEXT            NOT NULL DEFAULT '',
    created_by  BIGINT          NOT NULL,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ,
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_timeline_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_timeline_event (
    id             BIGSERIAL PRIMARY KEY,
    timeline_id    BIGINT          NOT NULL
        CONSTRAINT fk_artifact_timeline_event_timeline REFERENCES artifact_timeline(id) ON DELETE CASCADE,
    title          VARCHAR(300)    NOT NULL,
    description    TEXT            NOT NULL DEFAULT '',
    occurred_at    TIMESTAMPTZ,
    occurred_label VARCHAR(100)    NOT NULL DEFAULT '',
    position       SMALLINT        NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- artifact_lessons_learned  (type = LESSONS_LEARNED)
-- ============================================================================
CREATE TABLE artifact_lessons_learned (
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT          NOT NULL
        CONSTRAINT fk_artifact_lessons_learned_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    context     TEXT            NOT NULL DEFAULT '',
    created_by  BIGINT          NOT NULL,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ,
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_lessons_learned_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_lessons_learned_item (
    id                 BIGSERIAL PRIMARY KEY,
    lessons_learned_id BIGINT          NOT NULL
        CONSTRAINT fk_artifact_ll_item_lessons_learned REFERENCES artifact_lessons_learned(id) ON DELETE CASCADE,
    category           VARCHAR(16)     NOT NULL
        CONSTRAINT chk_artifact_ll_item_category CHECK (category IN ('sustain', 'improve', 'recommendation')),
    observation        TEXT            NOT NULL,
    discussion         TEXT            NOT NULL DEFAULT '',
    recommendation     TEXT            NOT NULL DEFAULT '',
    position           SMALLINT        NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- artifact_decision_brief  (type = DECISION_BRIEF)
-- ============================================================================
CREATE TABLE artifact_decision_brief (
    id             BIGSERIAL PRIMARY KEY,
    artifact_id    BIGINT          NOT NULL
        CONSTRAINT fk_artifact_decision_brief_artifact REFERENCES artifact(id) ON DELETE CASCADE,
    problem        TEXT            NOT NULL DEFAULT '',
    context        TEXT            NOT NULL DEFAULT '',
    risks          TEXT            NOT NULL DEFAULT '',
    recommendation TEXT            NOT NULL DEFAULT '',
    created_by     BIGINT          NOT NULL,
    created_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by     BIGINT,
    updated_at     TIMESTAMPTZ,
    deleted_by     BIGINT,
    deleted_at     TIMESTAMPTZ,
    CONSTRAINT uq_artifact_decision_brief_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_decision_brief_option (
    id                 BIGSERIAL PRIMARY KEY,
    decision_brief_id  BIGINT          NOT NULL
        CONSTRAINT fk_artifact_db_option_decision_brief REFERENCES artifact_decision_brief(id) ON DELETE CASCADE,
    title              VARCHAR(300)    NOT NULL,
    description        TEXT            NOT NULL DEFAULT '',
    pros               TEXT            NOT NULL DEFAULT '',
    cons               TEXT            NOT NULL DEFAULT '',
    is_recommended     BOOLEAN         NOT NULL DEFAULT FALSE,
    position           SMALLINT        NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Indexes — infrastructure tables
-- ============================================================================
CREATE INDEX idx_document_status          ON document(status);
CREATE INDEX idx_document_deleted_at      ON document(deleted_at);
CREATE INDEX idx_document_chat_active     ON document(chat_id) WHERE (deleted_at IS NULL);

CREATE INDEX idx_fragment_document_id     ON fragment(document_id);
CREATE INDEX idx_fragment_deleted_at      ON fragment(deleted_at);
CREATE UNIQUE INDEX idx_fragment_doc_index_active
    ON fragment (document_id, fragment_index) WHERE (deleted_at IS NULL);

CREATE INDEX IF NOT EXISTS fragments_bm25_idx
    ON fragment
    USING bm25 (id, content)
    WITH (key_field = 'id');

CREATE INDEX idx_chat_created_by_active ON chat (created_by) WHERE (deleted_at IS NULL);
CREATE INDEX idx_chat_deleted_at        ON chat(deleted_at);
CREATE INDEX idx_chat_source_assistant_id ON chat (source_assistant_id) WHERE source_assistant_id IS NOT NULL;

CREATE UNIQUE INDEX chat_membership_member_chat_unique
    ON chat_membership (member_id, chat_id)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_chat_membership_chat_member_status
    ON chat_membership (chat_id, member_id, status);
CREATE INDEX idx_chat_membership_chat_id  ON chat_membership(chat_id);
CREATE INDEX idx_chat_membership_member   ON chat_membership(member_id);
CREATE INDEX idx_chat_membership_deleted_at ON chat_membership(deleted_at);

CREATE INDEX idx_share_link_chat  ON chat_share_link(chat_id);
CREATE INDEX idx_share_link_token ON chat_share_link(token);

CREATE INDEX idx_notification_deleted_at      ON notification (deleted_at);
CREATE INDEX idx_notification_receiver_id     ON notification (receiver_id);
CREATE INDEX idx_notification_status          ON notification (status);
CREATE INDEX idx_notification_target_scope    ON notification (target_scope);
CREATE INDEX notif_receiver_status_created_idx
    ON notification (receiver_id, status, created_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX notif_receiver_event_type_created_idx
    ON notification (receiver_id, event_type, created_at DESC)
    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_receiver_event_key
    ON notification (receiver_id, event_key)
    WHERE event_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_notification_receiver_status
    ON notification (receiver_id, status)
    WHERE deleted_at IS NULL;
CREATE INDEX notif_severity_idx
    ON notification (severity)
    WHERE deleted_at IS NULL;
CREATE INDEX notification_preference_mute_until_idx
    ON notification_preference (mute_until)
    WHERE mute_until IS NOT NULL;
CREATE INDEX idx_notification_event_preference_user_id
    ON notification_event_preference (user_id);
CREATE INDEX idx_notification_dispatch_notification_id
    ON notification_dispatch (notification_id);
CREATE INDEX idx_notification_dispatch_receiver_id
    ON notification_dispatch (receiver_id);
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

CREATE UNIQUE INDEX idx_assistant_name_active ON assistant (name) WHERE deleted_at IS NULL;
CREATE INDEX idx_assistant_active     ON assistant (is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_assistant_created_by ON assistant (created_by);

CREATE INDEX idx_artifact_source_chat_created ON artifact (source_chat_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_source_chat_type    ON artifact (source_chat_id, type, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_owner_active        ON artifact (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_type                ON artifact (type);
CREATE INDEX idx_artifact_source_chat         ON artifact (source_chat_id);
CREATE INDEX idx_artifact_deleted_at          ON artifact (deleted_at);

CREATE INDEX idx_artifact_version_artifact ON artifact_version (artifact_id, version_number DESC);

CREATE INDEX idx_artifact_message_artifact    ON artifact_message (artifact_id);
CREATE INDEX idx_artifact_message_deleted_at  ON artifact_message (deleted_at);

CREATE INDEX idx_artifact_pin_artifact ON artifact_pin (artifact_id);
CREATE INDEX idx_artifact_pin_chat     ON artifact_pin (chat_id);

CREATE INDEX idx_artifact_bookmark_artifact ON artifact_bookmark (artifact_id);
CREATE INDEX idx_artifact_bookmark_user     ON artifact_bookmark (user_id);

CREATE INDEX idx_artifact_thread_reply_parent ON artifact_thread_reply (parent_artifact_id);

CREATE INDEX idx_artifact_feedback_artifact   ON artifact_feedback (artifact_id);
CREATE INDEX idx_artifact_feedback_created_at ON artifact_feedback (created_at);
CREATE INDEX idx_artifact_feedback_value      ON artifact_feedback (value);

CREATE INDEX idx_artifact_report_artifact    ON artifact_report (artifact_id);
CREATE INDEX idx_artifact_report_type        ON artifact_report (type);
CREATE INDEX idx_artifact_report_owner       ON artifact_report (created_by, created_at DESC) WHERE deleted_at IS NULL;

CREATE INDEX idx_artifact_checklist_artifact ON artifact_checklist (artifact_id);
CREATE INDEX idx_artifact_checklist_owner    ON artifact_checklist (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_checklist_section  ON artifact_checklist_section (checklist_id);
CREATE INDEX idx_artifact_checklist_item     ON artifact_checklist_item (section_id);

CREATE INDEX idx_artifact_quiz_artifact      ON artifact_quiz (artifact_id);
CREATE INDEX idx_artifact_quiz_owner         ON artifact_quiz (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_quiz_question_quiz ON artifact_quiz_question (quiz_id, position);
CREATE INDEX idx_artifact_quiz_option        ON artifact_quiz_option (question_id, position);

CREATE INDEX idx_artifact_timeline_artifact ON artifact_timeline (artifact_id);
CREATE INDEX idx_artifact_timeline_owner    ON artifact_timeline (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_timeline_event    ON artifact_timeline_event (timeline_id, position);

CREATE INDEX idx_artifact_lessons_learned_artifact ON artifact_lessons_learned (artifact_id);
CREATE INDEX idx_artifact_lessons_learned_owner    ON artifact_lessons_learned (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_ll_item_ll               ON artifact_lessons_learned_item (lessons_learned_id, position);

CREATE INDEX idx_artifact_decision_brief_artifact ON artifact_decision_brief (artifact_id);
CREATE INDEX idx_artifact_decision_brief_owner    ON artifact_decision_brief (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_db_option_brief         ON artifact_decision_brief_option (decision_brief_id, position);
