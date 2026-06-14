CREATE TABLE notification
(
    id           BIGSERIAL PRIMARY KEY,
    receiver_id  BIGINT       NOT NULL,
    event_type   VARCHAR(128) NOT NULL
        CONSTRAINT chk_notification_event_type CHECK (event_type IN (
            'chat.member.invited',
            'chat.member.removed',
            'chat.locked',
            'auth.password.changed',
            'auth.new_login',
            'document.processing.done',
            'document.processing.failed',
            'admin.broadcast',
            'system.announcement'
        )),
    message      VARCHAR(500) NOT NULL,
    data         JSONB        NOT NULL DEFAULT '{}'::jsonb,
    severity     VARCHAR(16)  NOT NULL DEFAULT 'info'
        CONSTRAINT chk_notification_severity CHECK (severity IN ('info', 'success', 'warning', 'critical')),
    link_url     VARCHAR(2048),
    actor_name   VARCHAR(255),
    status       VARCHAR(16)  NOT NULL DEFAULT 'unread'
        CONSTRAINT chk_notification_status CHECK (status IN ('unread', 'read')),
    read_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by   BIGINT,
    deleted_at   TIMESTAMPTZ,
    deleted_by   BIGINT
);

CREATE TABLE email_dispatch
(
    id           BIGSERIAL PRIMARY KEY,
    receiver_id  BIGINT       NOT NULL,
    event_type   VARCHAR(128) NOT NULL
        CONSTRAINT chk_email_dispatch_event_type CHECK (event_type IN (
            'chat.member.invited',
            'chat.member.removed',
            'chat.locked',
            'auth.password.changed',
            'auth.new_login',
            'document.processing.done',
            'document.processing.failed',
            'admin.broadcast',
            'system.announcement'
        )),
    status       VARCHAR(16)  NOT NULL DEFAULT 'pending'
        CONSTRAINT chk_email_dispatch_status CHECK (status IN ('pending', 'sent', 'failed', 'skipped')),
    attempt      INTEGER      NOT NULL DEFAULT 0,
    error        TEXT,
    payload      JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    sent_at      TIMESTAMPTZ
);

CREATE TABLE notification_preference
(
    user_id        BIGINT PRIMARY KEY,
    inapp_enabled  BOOLEAN     NOT NULL DEFAULT TRUE,
    email_enabled  BOOLEAN     NOT NULL DEFAULT TRUE,
    mute_until     TIMESTAMPTZ,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX idx_notification_deleted_at ON notification (deleted_at);
CREATE INDEX idx_notification_receiver_id ON notification (receiver_id);
CREATE INDEX idx_notification_status ON notification (status);
CREATE INDEX notif_receiver_status_created_idx
    ON notification (receiver_id, status, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX notif_receiver_event_type_created_idx
    ON notification (receiver_id, event_type, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_notification_receiver_status
    ON notification (receiver_id, status)
    WHERE deleted_at IS NULL;
CREATE INDEX notification_preference_mute_until_idx
    ON notification_preference (mute_until) WHERE mute_until IS NOT NULL;
CREATE INDEX idx_email_dispatch_receiver_id ON email_dispatch (receiver_id);
CREATE INDEX email_dispatch_receiver_created_idx
    ON email_dispatch (receiver_id, created_at DESC);
CREATE INDEX email_dispatch_status_idx
    ON email_dispatch (status, created_at DESC);
