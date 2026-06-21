CREATE TABLE assistant
(
    id             BIGSERIAL PRIMARY KEY,
    name           VARCHAR(256) NOT NULL,
    description    TEXT         NOT NULL DEFAULT '',
    system_prompt  TEXT         NOT NULL,
    response_style TEXT         NOT NULL DEFAULT '',
    avatar_emoji   VARCHAR(16)  NOT NULL DEFAULT '',
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by     BIGINT       NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by     BIGINT,
    updated_at     TIMESTAMPTZ,
    deleted_by     BIGINT,
    deleted_at     TIMESTAMPTZ
);

CREATE TABLE chat
(
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(255) NOT NULL,
    system_prompt       TEXT,
    response_style      TEXT,
    last_message_at     TIMESTAMPTZ,
    source_assistant_id BIGINT
        CONSTRAINT fk_chat_source_assistant REFERENCES assistant (id) ON DELETE SET NULL,
    created_by          BIGINT       NOT NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by          BIGINT,
    updated_at          TIMESTAMPTZ,
    deleted_by          BIGINT,
    deleted_at          TIMESTAMPTZ,
    tags                TEXT[]                   NOT NULL DEFAULT '{}',
    is_locked           BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE TABLE chat_membership
(
    id           BIGSERIAL PRIMARY KEY,
    member_id    BIGINT      NOT NULL,
    chat_id      BIGINT      NOT NULL
        CONSTRAINT fk_chat_membership_chat_id REFERENCES chat (id),
    status       VARCHAR(64) NOT NULL DEFAULT 'pending'
        CONSTRAINT chk_chat_membership_status CHECK (status IN ('active', 'pending')),
    joined_at    TIMESTAMPTZ,
    left_at      TIMESTAMPTZ,
    created_by   BIGINT      NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by   BIGINT,
    updated_at   TIMESTAMPTZ,
    deleted_by   BIGINT,
    deleted_at   TIMESTAMPTZ,
    pinned_at    TIMESTAMPTZ,
    archived_at  TIMESTAMPTZ,
    last_read_at TIMESTAMPTZ,
    role         VARCHAR(64) NOT NULL DEFAULT 'editor'
        CONSTRAINT chk_chat_membership_role CHECK (role IN ('owner', 'editor', 'reader'))
);

CREATE TABLE chat_share_link
(
    id         BIGSERIAL PRIMARY KEY,
    chat_id    BIGINT      NOT NULL REFERENCES chat (id) ON DELETE CASCADE,
    token      UUID        NOT NULL DEFAULT gen_random_uuid(),
    created_by BIGINT      NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_share_link_token UNIQUE (token)
);

CREATE TABLE artifact
(
    id             BIGSERIAL PRIMARY KEY,
    type           VARCHAR(32) NOT NULL
        CONSTRAINT chk_artifact_type CHECK (type IN (
                                                     'MESSAGE', 'REPORT', 'CHECKLIST', 'QUIZ',
                                                     'TIMELINE', 'LESSONS_LEARNED', 'DECISION_BRIEF',
                                                     'DOCUMENT_SUMMARY', 'DOCUMENT_ACTION'
            )),
    retrieve_context  BOOLEAN,
    process_documents BOOLEAN,
    document_ids      JSONB       NOT NULL DEFAULT '[]'::jsonb,
    fragments      JSONB,
    source_chat_id BIGINT      NOT NULL
        CONSTRAINT fk_artifact_source_chat REFERENCES chat (id) ON DELETE CASCADE,
    created_by     BIGINT      NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by     BIGINT,
    updated_at     TIMESTAMPTZ,
    deleted_by     BIGINT,
    deleted_at     TIMESTAMPTZ
);

CREATE TABLE artifact_pin
(
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT      NOT NULL
        CONSTRAINT fk_artifact_pin_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    created_by  BIGINT      NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT artifact_pin_unique UNIQUE (artifact_id)
);

CREATE TABLE artifact_bookmark
(
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT      NOT NULL
        CONSTRAINT fk_artifact_bookmark_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    created_by  BIGINT      NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_artifact_bookmark UNIQUE (artifact_id, created_by)
);

CREATE TABLE artifact_thread_reply
(
    id                 BIGSERIAL PRIMARY KEY,
    parent_artifact_id BIGINT      NOT NULL
        CONSTRAINT fk_artifact_thread_reply_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    message            TEXT        NOT NULL,
    created_by         BIGINT      NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by         BIGINT,
    updated_at         TIMESTAMPTZ,
    deleted_by         BIGINT,
    deleted_at         TIMESTAMPTZ
);

CREATE TABLE artifact_feedback
(
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT      NOT NULL
        CONSTRAINT fk_artifact_feedback_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    value       SMALLINT    NOT NULL
        CONSTRAINT chk_artifact_feedback_value CHECK (value IN (1, -1)),
    reason      VARCHAR(32)
        CONSTRAINT chk_artifact_feedback_reason CHECK (
            reason IS NULL OR reason IN (
                'incorrect', 'incomplete', 'off_topic', 'tone', 'too_long', 'hallucination', 'other'
            )
        ),
    comment     VARCHAR(500),
    created_by  BIGINT      NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_feedback UNIQUE (artifact_id, created_by)
);

CREATE TABLE artifact_feedback_evaluation
(
    id                  BIGSERIAL PRIMARY KEY,
    feedback_id         BIGINT NOT NULL UNIQUE
        CONSTRAINT fk_evaluation_feedback REFERENCES artifact_feedback (id) ON DELETE CASCADE,
    evaluated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    judge_model         VARCHAR(128) NOT NULL,
    failure_category    VARCHAR(64) NOT NULL
        CONSTRAINT chk_failure_category CHECK (
            failure_category IN ('retrieval_miss', 'hallucination', 'reasoning', 'style', 'incomplete', 'other', 'no_failure')
        ),
    failure_explanation TEXT NOT NULL,
    expected_output     TEXT NOT NULL,
    confidence_score    NUMERIC(3, 2)
        CONSTRAINT chk_confidence_score CHECK (confidence_score >= 0.00 AND confidence_score <= 1.00),
    raw_response        JSONB
);

CREATE TABLE artifact_message
(
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT      NOT NULL
        CONSTRAINT fk_artifact_message_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    message     TEXT        NOT NULL,
    sender_type VARCHAR(16) NOT NULL
        CONSTRAINT chk_artifact_message_sender CHECK (sender_type IN ('user', 'assistant')),
    created_by  BIGINT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_message_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_report
(
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT       NOT NULL
        CONSTRAINT fk_artifact_report_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    type        VARCHAR(16)  NOT NULL
        CONSTRAINT chk_artifact_report_type CHECK (type IN ('SITREP', 'INTSUM', 'OPORD')),
    title       VARCHAR(500) NOT NULL DEFAULT '',
    description TEXT         NOT NULL DEFAULT '',
    query       TEXT         NOT NULL DEFAULT '',
    content     TEXT         NOT NULL,
    created_by  BIGINT       NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_report_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_checklist
(
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT       NOT NULL
        CONSTRAINT fk_artifact_checklist_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    title       VARCHAR(500) NOT NULL DEFAULT '',
    description TEXT         NOT NULL DEFAULT '',
    query       TEXT         NOT NULL DEFAULT '',
    created_by  BIGINT       NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_checklist_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_checklist_section
(
    id           BIGSERIAL PRIMARY KEY,
    checklist_id BIGINT       NOT NULL
        CONSTRAINT fk_artifact_checklist_section_checklist REFERENCES artifact_checklist (id) ON DELETE CASCADE,
    title        VARCHAR(200) NOT NULL,
    position     SMALLINT     NOT NULL DEFAULT 0,
    created_by   BIGINT       NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by   BIGINT,
    deleted_at   TIMESTAMPTZ
);

CREATE TABLE artifact_checklist_item
(
    id         BIGSERIAL PRIMARY KEY,
    section_id BIGINT       NOT NULL
        CONSTRAINT fk_artifact_checklist_item_section REFERENCES artifact_checklist_section (id) ON DELETE CASCADE,
    text       VARCHAR(500) NOT NULL,
    is_checked BOOLEAN      NOT NULL DEFAULT FALSE,
    notes      TEXT         NOT NULL DEFAULT '',
    position   SMALLINT     NOT NULL DEFAULT 0,
    created_by BIGINT       NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by BIGINT,
    deleted_at TIMESTAMPTZ
);

CREATE TABLE artifact_quiz
(
    id           BIGSERIAL PRIMARY KEY,
    artifact_id  BIGINT       NOT NULL
        CONSTRAINT fk_artifact_quiz_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    title        VARCHAR(500) NOT NULL DEFAULT '',
    description  TEXT         NOT NULL DEFAULT '',
    query        TEXT         NOT NULL DEFAULT '',
    instructions TEXT         NOT NULL DEFAULT '',
    pass_score   SMALLINT,
    created_by   BIGINT       NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by   BIGINT,
    deleted_at   TIMESTAMPTZ,
    CONSTRAINT uq_artifact_quiz_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_quiz_question
(
    id          BIGSERIAL PRIMARY KEY,
    quiz_id     BIGINT      NOT NULL
        CONSTRAINT fk_artifact_quiz_question_quiz REFERENCES artifact_quiz (id) ON DELETE CASCADE,
    text        TEXT        NOT NULL,
    kind        VARCHAR(16) NOT NULL DEFAULT 'single'
        CONSTRAINT chk_artifact_quiz_question_kind CHECK (kind IN ('single', 'multiple', 'boolean')),
    explanation TEXT        NOT NULL DEFAULT '',
    position    SMALLINT    NOT NULL DEFAULT 0,
    created_by  BIGINT      NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE artifact_quiz_option
(
    id          BIGSERIAL PRIMARY KEY,
    question_id BIGINT       NOT NULL
        CONSTRAINT fk_artifact_quiz_option_question REFERENCES artifact_quiz_question (id) ON DELETE CASCADE,
    text        VARCHAR(500) NOT NULL,
    is_correct  BOOLEAN      NOT NULL DEFAULT FALSE,
    position    SMALLINT     NOT NULL DEFAULT 0,
    created_by  BIGINT       NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE artifact_timeline
(
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT       NOT NULL
        CONSTRAINT fk_artifact_timeline_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    title       VARCHAR(500) NOT NULL DEFAULT '',
    query       TEXT         NOT NULL DEFAULT '',
    summary     TEXT         NOT NULL DEFAULT '',
    created_by  BIGINT       NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_timeline_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_timeline_event
(
    id             BIGSERIAL PRIMARY KEY,
    timeline_id    BIGINT       NOT NULL
        CONSTRAINT fk_artifact_timeline_event_timeline REFERENCES artifact_timeline (id) ON DELETE CASCADE,
    title          VARCHAR(300) NOT NULL,
    description    TEXT         NOT NULL DEFAULT '',
    occurred_label VARCHAR(100) NOT NULL DEFAULT '',
    position       SMALLINT     NOT NULL DEFAULT 0,
    created_by     BIGINT       NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by     BIGINT,
    deleted_at     TIMESTAMPTZ
);

CREATE TABLE artifact_lessons_learned
(
    id          BIGSERIAL PRIMARY KEY,
    artifact_id BIGINT       NOT NULL
        CONSTRAINT fk_artifact_lessons_learned_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    title       VARCHAR(500) NOT NULL DEFAULT '',
    query       TEXT         NOT NULL DEFAULT '',
    context     TEXT         NOT NULL DEFAULT '',
    created_by  BIGINT       NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by  BIGINT,
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_artifact_lessons_learned_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_lessons_learned_item
(
    id                 BIGSERIAL PRIMARY KEY,
    lessons_learned_id BIGINT      NOT NULL
        CONSTRAINT fk_artifact_ll_item_lessons_learned REFERENCES artifact_lessons_learned (id) ON DELETE CASCADE,
    category           VARCHAR(16) NOT NULL
        CONSTRAINT chk_artifact_ll_item_category CHECK (category IN ('sustain', 'improve', 'recommendation')),
    observation        TEXT        NOT NULL,
    discussion         TEXT        NOT NULL DEFAULT '',
    recommendation     TEXT        NOT NULL DEFAULT '',
    position           SMALLINT    NOT NULL DEFAULT 0,
    created_by         BIGINT      NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_by         BIGINT,
    deleted_at         TIMESTAMPTZ
);

CREATE TABLE artifact_decision_brief
(
    id             BIGSERIAL PRIMARY KEY,
    artifact_id    BIGINT       NOT NULL
        CONSTRAINT fk_artifact_decision_brief_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    title          VARCHAR(500) NOT NULL DEFAULT '',
    query          TEXT         NOT NULL DEFAULT '',
    problem        TEXT         NOT NULL DEFAULT '',
    context        TEXT         NOT NULL DEFAULT '',
    risks          TEXT         NOT NULL DEFAULT '',
    recommendation TEXT         NOT NULL DEFAULT '',
    created_by     BIGINT       NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by     BIGINT,
    deleted_at     TIMESTAMPTZ,
    CONSTRAINT uq_artifact_decision_brief_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_decision_brief_option
(
    id                BIGSERIAL PRIMARY KEY,
    decision_brief_id BIGINT       NOT NULL
        CONSTRAINT fk_artifact_db_option_decision_brief REFERENCES artifact_decision_brief (id) ON DELETE CASCADE,
    title             VARCHAR(300) NOT NULL,
    pros              TEXT         NOT NULL DEFAULT '',
    cons              TEXT         NOT NULL DEFAULT '',
    is_recommended    BOOLEAN      NOT NULL DEFAULT FALSE,
    position          SMALLINT     NOT NULL DEFAULT 0,
    created_by        BIGINT       NOT NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by        BIGINT,
    deleted_at        TIMESTAMPTZ
);

CREATE TABLE artifact_document_summary
(
    id           BIGSERIAL PRIMARY KEY,
    artifact_id  BIGINT       NOT NULL
        CONSTRAINT fk_artifact_document_summary_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    title        VARCHAR(500) NOT NULL DEFAULT '',
    document_ids JSONB        NOT NULL DEFAULT '[]'::jsonb,
    summary      TEXT         NOT NULL DEFAULT '',
    created_by   BIGINT       NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by   BIGINT,
    deleted_at   TIMESTAMPTZ,
    CONSTRAINT uq_artifact_document_summary_artifact UNIQUE (artifact_id)
);

CREATE TABLE artifact_document_action
(
    id           BIGSERIAL PRIMARY KEY,
    artifact_id  BIGINT       NOT NULL
        CONSTRAINT fk_artifact_document_action_artifact REFERENCES artifact (id) ON DELETE CASCADE,
    title        VARCHAR(500) NOT NULL DEFAULT '',
    document_ids JSONB        NOT NULL DEFAULT '[]'::jsonb,
    instruction  TEXT         NOT NULL DEFAULT '',
    action       VARCHAR(32)
        CONSTRAINT chk_artifact_document_action_action CHECK (
            action IS NULL OR action IN (
                'summarize', 'essay', 'key_points', 'compare', 'analyze', 'explain', 'report'
            )
        ),
    result       TEXT         NOT NULL DEFAULT '',
    created_by   BIGINT       NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_by   BIGINT,
    deleted_at   TIMESTAMPTZ,
    CONSTRAINT uq_artifact_document_action_artifact UNIQUE (artifact_id)
);


CREATE INDEX idx_chat_created_by_active ON chat (created_by) WHERE (deleted_at IS NULL);
CREATE INDEX idx_chat_deleted_at ON chat (deleted_at);
CREATE INDEX idx_chat_source_assistant_id ON chat (source_assistant_id) WHERE source_assistant_id IS NOT NULL;

CREATE UNIQUE INDEX chat_membership_member_chat_unique
    ON chat_membership (member_id, chat_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_chat_membership_chat_member_status
    ON chat_membership (chat_id, member_id, status);
CREATE INDEX idx_chat_membership_chat_id ON chat_membership (chat_id);
CREATE INDEX idx_chat_membership_member ON chat_membership (member_id);
CREATE INDEX idx_chat_membership_deleted_at ON chat_membership (deleted_at);

CREATE INDEX idx_share_link_chat ON chat_share_link (chat_id);
CREATE INDEX idx_share_link_token ON chat_share_link (token);


CREATE UNIQUE INDEX idx_assistant_name_active ON assistant (name) WHERE deleted_at IS NULL;
CREATE INDEX idx_assistant_active ON assistant (is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_assistant_created_by ON assistant (created_by);

CREATE INDEX idx_artifact_source_chat_created ON artifact (source_chat_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_source_chat_type ON artifact (source_chat_id, type, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_owner_active ON artifact (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_type ON artifact (type);
CREATE INDEX idx_artifact_source_chat ON artifact (source_chat_id);
CREATE INDEX idx_artifact_deleted_at ON artifact (deleted_at);

CREATE INDEX idx_artifact_message_artifact ON artifact_message (artifact_id);
CREATE INDEX idx_artifact_message_deleted_at ON artifact_message (deleted_at);

CREATE INDEX idx_artifact_pin_artifact ON artifact_pin (artifact_id);
CREATE INDEX idx_artifact_pin_user ON artifact_pin (created_by);

CREATE INDEX idx_artifact_bookmark_artifact ON artifact_bookmark (artifact_id);
CREATE INDEX idx_artifact_bookmark_user ON artifact_bookmark (created_by);

CREATE INDEX idx_artifact_thread_reply_parent ON artifact_thread_reply (parent_artifact_id);
CREATE INDEX idx_artifact_thread_reply_deleted ON artifact_thread_reply (deleted_at);

CREATE INDEX idx_artifact_feedback_artifact ON artifact_feedback (artifact_id);
CREATE INDEX idx_artifact_feedback_created_at ON artifact_feedback (created_at);
CREATE INDEX idx_artifact_feedback_value ON artifact_feedback (value);

CREATE INDEX idx_artifact_report_artifact ON artifact_report (artifact_id);
CREATE INDEX idx_artifact_report_type ON artifact_report (type);
CREATE INDEX idx_artifact_report_owner ON artifact_report (created_by, created_at DESC) WHERE deleted_at IS NULL;

CREATE INDEX idx_artifact_checklist_artifact ON artifact_checklist (artifact_id);
CREATE INDEX idx_artifact_checklist_owner ON artifact_checklist (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_checklist_section ON artifact_checklist_section (checklist_id);
CREATE INDEX idx_artifact_checklist_item ON artifact_checklist_item (section_id);

CREATE INDEX idx_artifact_quiz_artifact ON artifact_quiz (artifact_id);
CREATE INDEX idx_artifact_quiz_owner ON artifact_quiz (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_quiz_question_quiz ON artifact_quiz_question (quiz_id, position);
CREATE INDEX idx_artifact_quiz_option ON artifact_quiz_option (question_id, position);

CREATE INDEX idx_artifact_timeline_artifact ON artifact_timeline (artifact_id);
CREATE INDEX idx_artifact_timeline_owner ON artifact_timeline (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_timeline_event ON artifact_timeline_event (timeline_id, position);

CREATE INDEX idx_artifact_lessons_learned_artifact ON artifact_lessons_learned (artifact_id);
CREATE INDEX idx_artifact_lessons_learned_owner ON artifact_lessons_learned (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_ll_item_ll ON artifact_lessons_learned_item (lessons_learned_id, position);

CREATE INDEX idx_artifact_decision_brief_artifact ON artifact_decision_brief (artifact_id);
CREATE INDEX idx_artifact_decision_brief_owner ON artifact_decision_brief (created_by, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifact_db_option_brief ON artifact_decision_brief_option (decision_brief_id, position);

CREATE INDEX idx_artifact_document_summary_artifact ON artifact_document_summary (artifact_id);
CREATE INDEX idx_artifact_document_summary_owner ON artifact_document_summary (created_by, created_at DESC) WHERE deleted_at IS NULL;

CREATE INDEX idx_artifact_document_action_artifact ON artifact_document_action (artifact_id);
CREATE INDEX idx_artifact_document_action_owner ON artifact_document_action (created_by, created_at DESC) WHERE deleted_at IS NULL;
