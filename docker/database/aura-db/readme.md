  -- 1. Reemplazar el unique constraint sin condición por uno condicional
  --    (permite re-agregar miembros que fueron removidos)
  ALTER TABLE chat_membership
      DROP CONSTRAINT chat_membership_member_chat_unique;

  CREATE UNIQUE INDEX chat_membership_member_chat_unique
      ON chat_membership (member_id, chat_id)
      WHERE deleted_at IS NULL;

  -- 2. Índice compuesto para is_active_member (se ejecuta en cada request y cada WS connect)                                                                                                                                       
  CREATE INDEX idx_chat_membership_chat_member_status
      ON chat_membership (chat_id, member_id, status);

    
  -- Índice compuesto para cursor pagination en ChatMessage                                                                                                                                                                         
  CREATE INDEX idx_chat_message_chat_created
      ON chat_message (chat_id, created_at DESC);