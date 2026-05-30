INSERT INTO classification_level (name, rank)
VALUES
    ('PUBLIC', 1),
    ('INTERNAL', 2),
    ('CONFIDENTIAL', 3),
    ('RESTRICTED', 4);

INSERT INTO compartment (name, description)
VALUES
    ('Program-Alpha', 'Necesidad de conocer programa Alpha (manual operativo general).'),
    ('Program-Bravo', 'Ámbito Bravo (información táctica de unidad).'),
    ('Program-Charlie', 'Integración sistemas Charlie (solo personal asignado).');

INSERT INTO chat (name, system_prompt, response_style, last_message_at, created_by, tags, is_ephemeral, is_locked)
VALUES
    (
        'Análisis — Reglamento interno Alpha',
        'Respondé de forma técnica y breve, basándote solo en el contexto aportado.',
        'conciso',
        NOW() - INTERVAL '2 hours',
        4,
        ARRAY['operations', 'alpha']::text[],
        FALSE,
        FALSE
    ),
    (
        'Consultas — Doctrina unidad Bravo',
        'Usá español formal; cuando cites normativa, indicá el apartado si lo conocés.',
        'formal',
        NOW() - INTERVAL '1 day',
        5,
        ARRAY['doctrine']::text[],
        FALSE,
        FALSE
    ),
    (
        'Demo — Sesión efímera',
        NULL,
        NULL,
        NULL,
        12,
        ARRAY['demo']::text[],
        TRUE,
        FALSE
    );

INSERT INTO chat_membership (member_id, chat_id, status, joined_at, left_at, created_by, role, last_read_at)
VALUES
    (4, 1, 'active',  NOW() - INTERVAL '8 days', NULL, 4, 'owner', NOW() - INTERVAL '30 minutes'),
    (5, 1, 'active',  NOW() - INTERVAL '7 days', NULL, 4, 'editor', NOW() - INTERVAL '1 hour'),
    (4, 2, 'active',  NOW() - INTERVAL '6 days', NULL, 5, 'editor', NOW() - INTERVAL '3 hours'),
    (5, 2, 'active',  NOW() - INTERVAL '5 days', NULL, 5, 'owner', NOW() - INTERVAL '2 hours'),
    (6, 2, 'pending', NULL, NULL, 5, 'reader', NULL),
    (12, 3, 'active', NOW() - INTERVAL '1 hour', NULL, 12, 'owner', NOW());

INSERT INTO chat_message (chat_id, message, sender_type, created_by)
VALUES
    (1, 'Resumí el alcance del capítulo 3 del reglamento.', 'user', 4),
    (1,
     'Capítulo 3 establece procedimientos operativos mínimos, roles de comando y comunicaciones internas ante incidentes clase B.',
     'system',
     NULL),
    (1, '¿Hay check-list para cierre?', 'user', 5),
    (1, 'Incluye lista de verificación en el anexo C (sección cerrar incidente): notificación, registro y relevo.', 'system', NULL),
    (2, 'Necesito la doctrina de escalamiento para unidades sur.', 'user', 4),
    (2,
     'Doctrina unidad sur: escalamiento en tres escalones (táctico → operativo → estratégico), con punto único de contacto por escalón.',
     'system',
     NULL),
    (3, 'Hola, esta conversación es solo de demostración.', 'user', 12);

INSERT INTO pinned_message (message_id, chat_id, pinned_by, pinned_at)
VALUES (2, 1, 4, NOW() - INTERVAL '12 hours');

INSERT INTO message_bookmark (message_id, user_id)
VALUES (4, 5);

INSERT INTO message_thread_reply (parent_message_id, message, created_by)
VALUES (
    2,
    'Anexo confirmado por la jefatura; conviene pegar referencia literal en el briefing.',
    5
);

INSERT INTO message_feedback (message_id, user_id, value)
VALUES (2, 4, 1);

INSERT INTO chat_share_link (chat_id, created_by, expires_at)
VALUES (1, 4, NOW() + INTERVAL '30 days');

INSERT INTO notification (receiver_id, message, type, target_scope, target_label, status, created_by)
VALUES
    (4,
     'Nuevo mensaje en el chat «Análisis — Reglamento interno Alpha».',
     'chat_message',
     'individual',
     'chat:1',
     'unread',
     5),
    (12,
     'Te invitaron como owner al chat «Demo — Sesión efímera».',
     'chat_invite',
     'individual',
     'chat:3',
     'unread',
     12);

INSERT INTO document_collection (name, classification_level_id, created_by)
VALUES
    ('Colección — Manuales de vuelo (2024)', 2, 4),
    ('Colección — Informes tácticos equipo sur', 3, 6),
    ('Colección — Material divulgativo público', 1, 4);

INSERT INTO document_collection_compartment (document_collection_id, compartment_id, created_by)
VALUES
    (1, 1, 4),
    (1, 2, 4),
    (2, 1, 6),
    (2, 2, 6),
    (2, 3, 6),
    (3, 1, 4);

INSERT INTO user_clearance (user_id, classification_level_id, created_by)
VALUES
    (4, 3, 4),
    (5, 1, 4),
    (6, 2, 6),
    (12, 2, 12);

INSERT INTO user_compartment (user_id, compartment_id, created_by)
VALUES
    (4, 1, 4),
    (4, 2, 4),
    (4, 3, 4),
    (5, 1, 5),
    (6, 1, 6),
    (6, 2, 6),
    (12, 1, 12);
