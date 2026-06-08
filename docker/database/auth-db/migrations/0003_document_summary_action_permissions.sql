-- Migration: add document_summary and document_action permissions
-- Run against an existing auth-db instance (data.sql already includes these for fresh volumes).

INSERT INTO permission (name, description) VALUES
    ('LLM_DOCUMENT_SUMMARY_GENERATE', 'Generación de resumen de documentos mediante LLM'),
    ('LLM_DOCUMENT_ACTION_GENERATE',  'Generación de acción sobre documentos mediante LLM'),
    ('LIST_DOCUMENT_SUMMARIES',        'Listar resúmenes de documentos'),
    ('GET_DOCUMENT_SUMMARY',           'Ver detalle de resumen de documentos'),
    ('UPDATE_DOCUMENT_SUMMARY',        'Actualizar resumen de documentos'),
    ('DELETE_DOCUMENT_SUMMARY',        'Eliminar resumen de documentos'),
    ('EXPORT_DOCUMENT_SUMMARY',        'Exportar resumen de documentos'),
    ('MANAGE_DOCUMENT_SUMMARIES',      'Listar todos los resúmenes de documentos (admin)'),
    ('MANAGE_EXPORT_DOCUMENT_SUMMARY', 'Exportar cualquier resumen de documentos (admin)'),
    ('LIST_DOCUMENT_ACTIONS',          'Listar acciones sobre documentos'),
    ('GET_DOCUMENT_ACTION',            'Ver detalle de acción sobre documentos'),
    ('UPDATE_DOCUMENT_ACTION',         'Actualizar acción sobre documentos'),
    ('DELETE_DOCUMENT_ACTION',         'Eliminar acción sobre documentos'),
    ('EXPORT_DOCUMENT_ACTION',         'Exportar acción sobre documentos'),
    ('MANAGE_DOCUMENT_ACTIONS',        'Listar todas las acciones sobre documentos (admin)'),
    ('MANAGE_EXPORT_DOCUMENT_ACTION',  'Exportar cualquier acción sobre documentos (admin)')
ON CONFLICT (name) DO NOTHING;

-- superadmin: all new permissions
INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON p.name IN (
    'LLM_DOCUMENT_SUMMARY_GENERATE',
    'LLM_DOCUMENT_ACTION_GENERATE',
    'LIST_DOCUMENT_SUMMARIES',
    'GET_DOCUMENT_SUMMARY',
    'UPDATE_DOCUMENT_SUMMARY',
    'DELETE_DOCUMENT_SUMMARY',
    'EXPORT_DOCUMENT_SUMMARY',
    'MANAGE_DOCUMENT_SUMMARIES',
    'MANAGE_EXPORT_DOCUMENT_SUMMARY',
    'LIST_DOCUMENT_ACTIONS',
    'GET_DOCUMENT_ACTION',
    'UPDATE_DOCUMENT_ACTION',
    'DELETE_DOCUMENT_ACTION',
    'EXPORT_DOCUMENT_ACTION',
    'MANAGE_DOCUMENT_ACTIONS',
    'MANAGE_EXPORT_DOCUMENT_ACTION'
)
WHERE r.name = 'superadmin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- admin: all new permissions
INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON p.name IN (
    'LLM_DOCUMENT_SUMMARY_GENERATE',
    'LLM_DOCUMENT_ACTION_GENERATE',
    'LIST_DOCUMENT_SUMMARIES',
    'GET_DOCUMENT_SUMMARY',
    'UPDATE_DOCUMENT_SUMMARY',
    'DELETE_DOCUMENT_SUMMARY',
    'EXPORT_DOCUMENT_SUMMARY',
    'MANAGE_DOCUMENT_SUMMARIES',
    'MANAGE_EXPORT_DOCUMENT_SUMMARY',
    'LIST_DOCUMENT_ACTIONS',
    'GET_DOCUMENT_ACTION',
    'UPDATE_DOCUMENT_ACTION',
    'DELETE_DOCUMENT_ACTION',
    'EXPORT_DOCUMENT_ACTION',
    'MANAGE_DOCUMENT_ACTIONS',
    'MANAGE_EXPORT_DOCUMENT_ACTION'
)
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- user: non-MANAGE permissions only
INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON p.name IN (
    'LLM_DOCUMENT_SUMMARY_GENERATE',
    'LLM_DOCUMENT_ACTION_GENERATE',
    'LIST_DOCUMENT_SUMMARIES',
    'GET_DOCUMENT_SUMMARY',
    'UPDATE_DOCUMENT_SUMMARY',
    'DELETE_DOCUMENT_SUMMARY',
    'EXPORT_DOCUMENT_SUMMARY',
    'LIST_DOCUMENT_ACTIONS',
    'GET_DOCUMENT_ACTION',
    'UPDATE_DOCUMENT_ACTION',
    'DELETE_DOCUMENT_ACTION',
    'EXPORT_DOCUMENT_ACTION'
)
WHERE r.name = 'user'
ON CONFLICT (role_id, permission_id) DO NOTHING;
