-- Asigna GET_DOCUMENT al rol user (permite que los usuarios consulten el estado de sus documentos)
INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON p.name = 'GET_DOCUMENT'
WHERE r.name = 'user'
ON CONFLICT (role_id, permission_id) DO NOTHING;
