-- ============================================================================
-- Migration 0001 (auth-db): artifact permissions
--
-- Idempotent. Safe to run on an EXISTING auth-db (data.sql only runs on a fresh
-- volume). Grants the new artifact permissions:
--   * superadmin + admin -> all artifact permissions (incl. admin-wide MANAGE)
--   * user               -> all artifact permissions except MANAGE_ARTIFACTS
--
-- Apply with, e.g.:
--   Get-Content database/auth-db/migrations/0001_artifact_permissions.sql | `
--     docker exec -i auth-db psql -U <user> -d <db>
-- ============================================================================

INSERT INTO permission (name, description) VALUES
    ('LIST_ARTIFACTS', 'Listar artefactos'),
    ('CREATE_ARTIFACT', 'Crear artefacto'),
    ('GET_ARTIFACT', 'Ver detalle de artefacto'),
    ('UPDATE_ARTIFACT', 'Actualizar artefacto'),
    ('DELETE_ARTIFACT', 'Eliminar artefacto'),
    ('LIST_ARTIFACT_VERSIONS', 'Listar versiones de un artefacto'),
    ('MANAGE_ARTIFACTS', 'Listar todos los artefactos (admin)')
ON CONFLICT (name) DO NOTHING;

-- superadmin + admin: every artifact permission
INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON p.name IN (
    'LIST_ARTIFACTS', 'CREATE_ARTIFACT', 'GET_ARTIFACT', 'UPDATE_ARTIFACT',
    'DELETE_ARTIFACT', 'LIST_ARTIFACT_VERSIONS', 'MANAGE_ARTIFACTS'
)
WHERE r.name IN ('superadmin', 'admin')
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- user: artifact permissions except the admin-wide MANAGE_ARTIFACTS
INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON p.name IN (
    'LIST_ARTIFACTS', 'CREATE_ARTIFACT', 'GET_ARTIFACT', 'UPDATE_ARTIFACT',
    'DELETE_ARTIFACT', 'LIST_ARTIFACT_VERSIONS'
)
WHERE r.name = 'user'
ON CONFLICT (role_id, permission_id) DO NOTHING;
