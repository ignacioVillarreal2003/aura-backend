-- ============================================================================
-- Migration 0002 (auth-db): timeline, quiz, lessons-learned, decision-brief
--                           permissions + LLM generate permissions
--
-- Idempotent. Safe to run on an EXISTING auth-db (data.sql only runs on a
-- fresh volume).
--   * superadmin + admin -> all new permissions (incl. MANAGE_* / MANAGE_EXPORT_*)
--   * user               -> LLM generate + LIST/GET/UPDATE/DELETE/EXPORT
--                           (no CREATE_* ni MANAGE_* por rol)
--
-- Apply with:
--   Get-Content docker/database/auth-db/migrations/0002_artifact_type_permissions.sql | `
--     docker exec -i auth-db psql -U <user> -d <db>
-- ============================================================================

-- ─── 1. Permissions ─────────────────────────────────────────────────────────

INSERT INTO permission (name, description) VALUES
    -- LLM generate
    ('LLM_TIMELINE_GENERATE',        'Generación de línea de tiempo mediante LLM'),
    ('LLM_QUIZ_GENERATE',            'Generación de quiz mediante LLM'),
    ('LLM_LESSONS_LEARNED_GENERATE', 'Generación de lecciones aprendidas mediante LLM'),
    ('LLM_DECISION_BRIEF_GENERATE',  'Generación de decision brief mediante LLM'),
    -- Timelines
    ('LIST_TIMELINES',               'Listar líneas de tiempo'),
    ('CREATE_TIMELINE',              'Crear línea de tiempo'),
    ('GET_TIMELINE',                 'Ver detalle de línea de tiempo'),
    ('UPDATE_TIMELINE',              'Actualizar línea de tiempo'),
    ('DELETE_TIMELINE',              'Eliminar línea de tiempo'),
    ('EXPORT_TIMELINE',              'Exportar línea de tiempo'),
    ('MANAGE_TIMELINES',             'Listar todas las líneas de tiempo (admin)'),
    ('MANAGE_EXPORT_TIMELINE',       'Exportar cualquier línea de tiempo (admin)'),
    -- Quizzes
    ('LIST_QUIZZES',                 'Listar quizzes'),
    ('CREATE_QUIZ',                  'Crear quiz'),
    ('GET_QUIZ',                     'Ver detalle de quiz'),
    ('UPDATE_QUIZ',                  'Actualizar quiz'),
    ('DELETE_QUIZ',                  'Eliminar quiz'),
    ('EXPORT_QUIZ',                  'Exportar quiz'),
    ('MANAGE_QUIZZES',               'Listar todos los quizzes (admin)'),
    ('MANAGE_EXPORT_QUIZ',           'Exportar cualquier quiz (admin)'),
    -- Lessons Learned
    ('LIST_LESSONS_LEARNED',         'Listar lecciones aprendidas'),
    ('CREATE_LESSONS_LEARNED',       'Crear lecciones aprendidas'),
    ('GET_LESSONS_LEARNED',          'Ver detalle de lecciones aprendidas'),
    ('UPDATE_LESSONS_LEARNED',       'Actualizar lecciones aprendidas'),
    ('DELETE_LESSONS_LEARNED',       'Eliminar lecciones aprendidas'),
    ('EXPORT_LESSONS_LEARNED',       'Exportar lecciones aprendidas'),
    ('MANAGE_LESSONS_LEARNED',       'Listar todas las lecciones aprendidas (admin)'),
    ('MANAGE_EXPORT_LESSONS_LEARNED','Exportar cualquier lección aprendida (admin)'),
    -- Decision Briefs
    ('LIST_DECISION_BRIEFS',         'Listar decision briefs'),
    ('CREATE_DECISION_BRIEF',        'Crear decision brief'),
    ('GET_DECISION_BRIEF',           'Ver detalle de decision brief'),
    ('UPDATE_DECISION_BRIEF',        'Actualizar decision brief'),
    ('DELETE_DECISION_BRIEF',        'Eliminar decision brief'),
    ('EXPORT_DECISION_BRIEF',        'Exportar decision brief'),
    ('MANAGE_DECISION_BRIEFS',       'Listar todos los decision briefs (admin)'),
    ('MANAGE_EXPORT_DECISION_BRIEF', 'Exportar cualquier decision brief (admin)'),
    -- Feedback analytics
    ('VIEW_FEEDBACK_ANALYTICS',      'Ver analítica de feedback (admin)')
ON CONFLICT (name) DO NOTHING;

-- ─── 2. superadmin + admin: todos los permisos nuevos ───────────────────────

INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON p.name IN (
    'LLM_TIMELINE_GENERATE',
    'LLM_QUIZ_GENERATE',
    'LLM_LESSONS_LEARNED_GENERATE',
    'LLM_DECISION_BRIEF_GENERATE',
    'LIST_TIMELINES',    'CREATE_TIMELINE',    'GET_TIMELINE',    'UPDATE_TIMELINE',    'DELETE_TIMELINE',    'EXPORT_TIMELINE',    'MANAGE_TIMELINES',    'MANAGE_EXPORT_TIMELINE',
    'LIST_QUIZZES',      'CREATE_QUIZ',        'GET_QUIZ',        'UPDATE_QUIZ',        'DELETE_QUIZ',        'EXPORT_QUIZ',        'MANAGE_QUIZZES',      'MANAGE_EXPORT_QUIZ',
    'LIST_LESSONS_LEARNED','CREATE_LESSONS_LEARNED','GET_LESSONS_LEARNED','UPDATE_LESSONS_LEARNED','DELETE_LESSONS_LEARNED','EXPORT_LESSONS_LEARNED','MANAGE_LESSONS_LEARNED','MANAGE_EXPORT_LESSONS_LEARNED',
    'LIST_DECISION_BRIEFS','CREATE_DECISION_BRIEF','GET_DECISION_BRIEF','UPDATE_DECISION_BRIEF','DELETE_DECISION_BRIEF','EXPORT_DECISION_BRIEF','MANAGE_DECISION_BRIEFS','MANAGE_EXPORT_DECISION_BRIEF',
    'VIEW_FEEDBACK_ANALYTICS'
)
WHERE r.name IN ('superadmin', 'admin')
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ─── 3. user: LLM generate + LIST/GET/UPDATE/DELETE/EXPORT (sin MANAGE_*) ──

INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON p.name IN (
    'LLM_TIMELINE_GENERATE',
    'LLM_QUIZ_GENERATE',
    'LLM_LESSONS_LEARNED_GENERATE',
    'LLM_DECISION_BRIEF_GENERATE',
    'LIST_TIMELINES',    'GET_TIMELINE',    'UPDATE_TIMELINE',    'DELETE_TIMELINE',    'EXPORT_TIMELINE',
    'LIST_QUIZZES',      'GET_QUIZ',        'UPDATE_QUIZ',        'DELETE_QUIZ',        'EXPORT_QUIZ',
    'LIST_LESSONS_LEARNED','GET_LESSONS_LEARNED','UPDATE_LESSONS_LEARNED','DELETE_LESSONS_LEARNED','EXPORT_LESSONS_LEARNED',
    'LIST_DECISION_BRIEFS','GET_DECISION_BRIEF','UPDATE_DECISION_BRIEF','DELETE_DECISION_BRIEF','EXPORT_DECISION_BRIEF'
)
WHERE r.name = 'user'
ON CONFLICT (role_id, permission_id) DO NOTHING;
