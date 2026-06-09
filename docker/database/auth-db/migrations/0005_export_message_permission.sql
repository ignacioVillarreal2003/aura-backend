-- ============================================================================
-- Migration 0005 (auth-db): EXPORT_MESSAGE permission
--
-- Idempotent. Safe to run on an existing auth-db.
-- Adds EXPORT_MESSAGE to the permission table and grants it to
-- superadmin, admin, and user roles.
--
-- Apply with:
--   Get-Content docker/database/auth-db/migrations/0005_export_message_permission.sql | `
--     docker exec -i auth-db psql -U <user> -d <db>
-- ============================================================================

INSERT INTO permission (name, description) VALUES
    ('EXPORT_MESSAGE', 'Exportar mensaje individual')
ON CONFLICT (name) DO NOTHING;

INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON p.name = 'EXPORT_MESSAGE'
WHERE r.name IN ('superadmin', 'admin', 'user')
ON CONFLICT (role_id, permission_id) DO NOTHING;
