-- ============================================================================
-- Aura Chat Service - Database Migration
-- Version: 001
-- Description: Create chat tables (Conversation, Message, Attachment, ToolCall)
-- ============================================================================

-- Enable UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

-- Conversation status
DO $$ BEGIN
    CREATE TYPE conversation_status AS ENUM ('active', 'archived');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Message role (compatible with OpenAI)
DO $$ BEGIN
    CREATE TYPE message_role AS ENUM ('system', 'user', 'assistant', 'tool');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Message status
DO $$ BEGIN
    CREATE TYPE message_status AS ENUM ('draft', 'streaming', 'complete', 'error');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Attachment type
DO $$ BEGIN
    CREATE TYPE attachment_type AS ENUM ('image', 'file', 'audio', 'video');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Tool call status
DO $$ BEGIN
    CREATE TYPE tool_call_status AS ENUM ('pending', 'executing', 'completed', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- TABLE: conversation
-- ============================================================================

CREATE TABLE IF NOT EXISTS conversation (
    -- Primary key
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Conversation data
    title               VARCHAR(255),
    system_prompt       TEXT,
    model               VARCHAR(100) NOT NULL DEFAULT 'default',
    status              conversation_status NOT NULL DEFAULT 'active',
    
    -- Extensible metadata (JSON)
    metadata            JSONB NOT NULL DEFAULT '{}',
    
    -- Denormalized counters for performance
    message_count       INTEGER NOT NULL DEFAULT 0,
    total_tokens        INTEGER NOT NULL DEFAULT 0,
    
    -- Owner (foreign key to auth_user in auth_db)
    user_id             BIGINT NOT NULL,
    
    -- Audit fields
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE,
    deleted_at          TIMESTAMP WITH TIME ZONE  -- Soft delete
);

-- Indexes for conversation
CREATE INDEX IF NOT EXISTS idx_conversation_user_id 
    ON conversation(user_id) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_conversation_user_created 
    ON conversation(user_id, created_at DESC) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_conversation_status 
    ON conversation(status) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_conversation_deleted_at 
    ON conversation(deleted_at) 
    WHERE deleted_at IS NOT NULL;

-- GIN index for metadata JSONB queries
CREATE INDEX IF NOT EXISTS idx_conversation_metadata 
    ON conversation USING GIN (metadata);

-- ============================================================================
-- TABLE: message
-- ============================================================================

CREATE TABLE IF NOT EXISTS message (
    -- Primary key
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Foreign key to conversation
    conversation_id     UUID NOT NULL,
    
    -- Message content
    role                message_role NOT NULL,
    content             TEXT,  -- Can be null if there are tool_calls
    
    -- Status
    status              message_status NOT NULL DEFAULT 'complete',
    
    -- Token tracking (optional)
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    total_tokens        INTEGER,
    
    -- For assistant responses
    model_used          VARCHAR(100),
    finish_reason       VARCHAR(50),  -- stop, length, tool_calls, error
    
    -- Extensible metadata
    metadata            JSONB NOT NULL DEFAULT '{}',
    
    -- For tool messages (response to a tool call)
    tool_call_id        VARCHAR(100),
    
    -- Order within conversation
    sequence_number     INTEGER NOT NULL,
    
    -- Audit fields
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE,
    deleted_at          TIMESTAMP WITH TIME ZONE,  -- Soft delete
    
    -- Foreign key constraint
    CONSTRAINT fk_message_conversation 
        FOREIGN KEY (conversation_id) 
        REFERENCES conversation(id) 
        ON DELETE CASCADE
);

-- Indexes for message
CREATE INDEX IF NOT EXISTS idx_message_conversation_id 
    ON message(conversation_id) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_message_conversation_seq 
    ON message(conversation_id, sequence_number) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_message_role 
    ON message(conversation_id, role) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_message_status 
    ON message(status) 
    WHERE status IN ('draft', 'streaming');

CREATE INDEX IF NOT EXISTS idx_message_tool_call_id 
    ON message(tool_call_id) 
    WHERE tool_call_id IS NOT NULL;

-- GIN index for metadata JSONB queries
CREATE INDEX IF NOT EXISTS idx_message_metadata 
    ON message USING GIN (metadata);

-- ============================================================================
-- TABLE: attachment
-- ============================================================================

CREATE TABLE IF NOT EXISTS attachment (
    -- Primary key
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Foreign key to message
    message_id          UUID NOT NULL,
    
    -- File information
    file_name           VARCHAR(255) NOT NULL,
    file_type           attachment_type NOT NULL,
    mime_type           VARCHAR(100) NOT NULL,
    file_size           BIGINT NOT NULL,  -- Size in bytes
    storage_path        VARCHAR(500) NOT NULL,  -- Path in MinIO/S3
    
    -- Additional metadata (image dimensions, audio duration, etc.)
    metadata            JSONB NOT NULL DEFAULT '{}',
    
    -- For images processed by vision models
    description         TEXT,
    
    -- Audit fields
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMP WITH TIME ZONE,  -- Soft delete
    
    -- Foreign key constraint
    CONSTRAINT fk_attachment_message 
        FOREIGN KEY (message_id) 
        REFERENCES message(id) 
        ON DELETE CASCADE
);

-- Indexes for attachment
CREATE INDEX IF NOT EXISTS idx_attachment_message_id 
    ON attachment(message_id) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_attachment_type 
    ON attachment(file_type) 
    WHERE deleted_at IS NULL;

-- ============================================================================
-- TABLE: tool_call
-- ============================================================================

CREATE TABLE IF NOT EXISTS tool_call (
    -- Primary key
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Foreign key to message (the assistant message that requested the tool)
    message_id          UUID NOT NULL,
    
    -- Tool call ID generated by the LLM
    tool_call_id        VARCHAR(100) NOT NULL UNIQUE,
    
    -- Tool information
    tool_type           VARCHAR(50) NOT NULL DEFAULT 'function',
    function_name       VARCHAR(255) NOT NULL,
    function_args       JSONB NOT NULL,
    
    -- Execution result
    status              tool_call_status NOT NULL DEFAULT 'pending',
    result              TEXT,
    error_message       TEXT,
    
    -- Timing
    started_at          TIMESTAMP WITH TIME ZONE,
    completed_at        TIMESTAMP WITH TIME ZONE,
    
    -- Audit fields
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Foreign key constraint
    CONSTRAINT fk_tool_call_message 
        FOREIGN KEY (message_id) 
        REFERENCES message(id) 
        ON DELETE CASCADE
);

-- Indexes for tool_call
CREATE INDEX IF NOT EXISTS idx_tool_call_message_id 
    ON tool_call(message_id);

CREATE INDEX IF NOT EXISTS idx_tool_call_tool_call_id 
    ON tool_call(tool_call_id);

CREATE INDEX IF NOT EXISTS idx_tool_call_status 
    ON tool_call(status) 
    WHERE status IN ('pending', 'executing');

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for conversation.updated_at
DROP TRIGGER IF EXISTS update_conversation_updated_at ON conversation;
CREATE TRIGGER update_conversation_updated_at
    BEFORE UPDATE ON conversation
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for message.updated_at
DROP TRIGGER IF EXISTS update_message_updated_at ON message;
CREATE TRIGGER update_message_updated_at
    BEFORE UPDATE ON message
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to update conversation counters
CREATE OR REPLACE FUNCTION update_conversation_counters()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE conversation 
        SET 
            message_count = message_count + 1,
            total_tokens = total_tokens + COALESCE(NEW.total_tokens, 0),
            updated_at = NOW()
        WHERE id = NEW.conversation_id;
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        -- Only update tokens if they changed
        IF OLD.total_tokens IS DISTINCT FROM NEW.total_tokens THEN
            UPDATE conversation 
            SET 
                total_tokens = total_tokens - COALESCE(OLD.total_tokens, 0) + COALESCE(NEW.total_tokens, 0),
                updated_at = NOW()
            WHERE id = NEW.conversation_id;
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE conversation 
        SET 
            message_count = message_count - 1,
            total_tokens = total_tokens - COALESCE(OLD.total_tokens, 0),
            updated_at = NOW()
        WHERE id = OLD.conversation_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ language 'plpgsql';

-- Trigger for conversation counters
DROP TRIGGER IF EXISTS update_conversation_counters_trigger ON message;
CREATE TRIGGER update_conversation_counters_trigger
    AFTER INSERT OR UPDATE OR DELETE ON message
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_counters();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE conversation IS 'Chat conversations/threads';
COMMENT ON COLUMN conversation.id IS 'Unique identifier (UUID v4)';
COMMENT ON COLUMN conversation.title IS 'User-defined or auto-generated title';
COMMENT ON COLUMN conversation.system_prompt IS 'Custom system prompt for this conversation';
COMMENT ON COLUMN conversation.model IS 'LLM model to use (e.g., llama3, gpt-4)';
COMMENT ON COLUMN conversation.status IS 'active or archived';
COMMENT ON COLUMN conversation.metadata IS 'Extensible JSON metadata';
COMMENT ON COLUMN conversation.message_count IS 'Denormalized message count';
COMMENT ON COLUMN conversation.total_tokens IS 'Denormalized total tokens consumed';
COMMENT ON COLUMN conversation.user_id IS 'Owner user ID (FK to auth_user)';
COMMENT ON COLUMN conversation.deleted_at IS 'Soft delete timestamp';

COMMENT ON TABLE message IS 'Individual messages within a conversation';
COMMENT ON COLUMN message.role IS 'system, user, assistant, or tool';
COMMENT ON COLUMN message.content IS 'Message content (can be null for tool_calls)';
COMMENT ON COLUMN message.status IS 'draft, streaming, complete, or error';
COMMENT ON COLUMN message.finish_reason IS 'stop, length, tool_calls, or error';
COMMENT ON COLUMN message.tool_call_id IS 'For tool messages: ID of the tool call being responded to';
COMMENT ON COLUMN message.sequence_number IS 'Order within the conversation';

COMMENT ON TABLE attachment IS 'File attachments to messages';
COMMENT ON COLUMN attachment.storage_path IS 'Path in object storage (MinIO/S3)';
COMMENT ON COLUMN attachment.description IS 'AI-generated description of the file';

COMMENT ON TABLE tool_call IS 'Function/tool calls requested by the assistant';
COMMENT ON COLUMN tool_call.tool_call_id IS 'Unique ID generated by the LLM';
COMMENT ON COLUMN tool_call.function_args IS 'JSON arguments for the function';
COMMENT ON COLUMN tool_call.result IS 'Result of the tool execution';

