INSERT INTO permission (name, description) VALUES
    ('INGEST_DOCUMENT', 'Ingerir o subir un documento al pipeline (carga e ingesta)'),
    ('GET_DOCUMENT', 'Ver el detalle de un documento'),
    ('LIST_DOCUMENTS', 'Listar documentos en general'),
    ('LIST_DOCUMENTS_BY_CHAT', 'Listar documentos asociados a un chat'),
    ('DOWNLOAD_DOCUMENT', 'Descargar el archivo de un documento'),
    ('SOFT_DELETE_DOCUMENT', 'Eliminar lógicamente (soft delete) un documento'),
    ('SOFT_DELETE_DOCUMENTS_BY_CHAT', 'Eliminar lógicamente documentos de un chat'),
    ('POST_PROCESS_DOCUMENTS_START_ALL', 'Iniciar el post-proceso masivo de documentos'),
    ('POST_PROCESS_DOCUMENTS_START', 'Iniciar el post-proceso de un documento concreto'),
    ('POST_PROCESS_DOCUMENTS_STATUS', 'Consultar el estado del post-proceso de documentos'),
    ('POST_PROCESS_DOCUMENTS_STOP', 'Detener el post-proceso de documentos'),
    ('POST_PROCESS_FRAGMENTS_START_ALL', 'Iniciar el post-proceso masivo de fragmentos'),
    ('POST_PROCESS_FRAGMENTS_START', 'Iniciar el post-proceso de un fragmento o lote'),
    ('POST_PROCESS_FRAGMENTS_STATUS', 'Consultar el estado del post-proceso de fragmentos'),
    ('POST_PROCESS_FRAGMENTS_STOP', 'Detener el post-proceso de fragmentos'),
    ('LIST_CONTEXT_FRAGMENTS_BY_QUESTION', 'Obtener fragmentos de contexto según una pregunta'),
    ('LIST_CONTEXT_FRAGMENTS_BY_DOCUMENTS', 'Obtener fragmentos de contexto a partir de documentos'),
    ('GRAPH_QUERY', 'Consulta sobre grafos derivados'),
    ('GRAPH_ENTITY', 'Operaciones de entidad sobre grafo'),
    ('GRAPH_PATH', 'Consulta de rutas en grafo'),
    ('LIST_DOCUMENT_COLLECTIONS', 'Listar colecciones documentales MAC'),
    ('CREATE_DOCUMENT_COLLECTION', 'Crear colección documental'),
    ('GET_DOCUMENT_COLLECTION', 'Ver detalle de colección documental'),
    ('UPDATE_DOCUMENT_COLLECTION', 'Actualizar colección documental'),
    ('DELETE_DOCUMENT_COLLECTION', 'Eliminar colección documental'),
    ('LIST_DOCUMENT_COLLECTION_DOCUMENTS', 'Listar documentos enlazados a una colección'),
    ('ADD_DOCUMENT_COLLECTION_DOCUMENT', 'Añadir documento a una colección'),
    ('REMOVE_DOCUMENT_COLLECTION_DOCUMENT', 'Quitar documento de una colección'),
    ('LIST_CLASSIFICATION_LEVELS', 'Listar niveles de clasificación'),
    ('CREATE_CLASSIFICATION_LEVEL', 'Crear nivel de clasificación'),
    ('GET_CLASSIFICATION_LEVEL', 'Ver nivel de clasificación'),
    ('UPDATE_CLASSIFICATION_LEVEL', 'Actualizar nivel de clasificación'),
    ('DELETE_CLASSIFICATION_LEVEL', 'Eliminar nivel de clasificación'),
    ('LIST_COMPARTMENTS', 'Listar compartimentos'),
    ('CREATE_COMPARTMENT', 'Crear compartimento'),
    ('GET_COMPARTMENT', 'Ver compartimento'),
    ('UPDATE_COMPARTMENT', 'Actualizar compartimento'),
    ('DELETE_COMPARTMENT', 'Eliminar compartimento'),
    ('GET_USER_AUTHORIZATION', 'Ver autorización MAC de usuario'),
    ('SET_USER_CLEARANCE', 'Asignar nivel de clasificación del usuario'),
    ('DELETE_USER_CLEARANCE', 'Quitar nivel de clasificación del usuario'),
    ('LIST_USER_COMPARTMENTS', 'Listar compartimentos del usuario'),
    ('ADD_USER_COMPARTMENT', 'Asignar compartimento al usuario'),
    ('REMOVE_USER_COMPARTMENT', 'Quitar compartimento del usuario'),
    ('GET_USER_ACCESSIBLE_COLLECTIONS', 'Listar colecciones documentales accesibles para el usuario'),
    ('LLM_DOCUMENT_QUESTION', 'Pregunta LLM contra documentación'),
    ('LLM_DOCUMENT_QUESTION_STREAM', 'Pregunta LLM contra documentación (streaming)'),
    ('LLM_DOCUMENT_SUMMARY', 'Resumen de documento mediante LLM'),
    ('LLM_DOCUMENT_ACTION', 'Acción automatizada sobre documento'),
    ('LLM_AGENT', 'Ejecución de agentes LLM'),
    ('LLM_DOCUMENT_CLASSIFY', 'Clasificación de documentos vía LLM'),
    ('LLM_FRAGMENT_ENRICH', 'Enriquecimiento de fragmentos'),
    ('LLM_GRAPH_EXTRACTION', 'Extracción de grafo vía LLM'),
    ('LLM_GRAPH_QUERY_TRANSLATION', 'Traducción de consulta a grafo'),
    ('LIST_CHATS', 'Listar chats'),
    ('LIST_MY_CHATS', 'Listar chats creados por el usuario'),
    ('LIST_ARCHIVED_CHATS', 'Listar chats archivados para el usuario'),
    ('CREATE_CHAT', 'Crear chat'),
    ('GET_CHAT', 'Ver chat'),
    ('UPDATE_CHAT', 'Actualizar chat'),
    ('DELETE_CHAT', 'Eliminar chat'),
    ('PIN_CHAT', 'Fijar/desfijar chat en lista'),
    ('ARCHIVE_CHAT', 'Archivar chats'),
    ('UNARCHIVE_CHAT', 'Desarchivar chats'),
    ('LOCK_CHAT', 'Bloquear envío en chat'),
    ('MUTE_CHAT', 'Silenciar chat para el usuario'),
    ('LIST_SHARE_LINKS', 'Listar enlaces de compartición'),
    ('CREATE_SHARE_LINK', 'Crear enlace de compartición'),
    ('DELETE_SHARE_LINK', 'Eliminar enlace de compartición'),
    ('LIST_WEBHOOKS', 'Listar webhooks del chat'),
    ('CREATE_WEBHOOK', 'Crear webhook'),
    ('UPDATE_WEBHOOK', 'Actualizar webhook'),
    ('DELETE_WEBHOOK', 'Eliminar webhook'),
    ('LIST_MEMBERS', 'Listar miembros del chat'),
    ('ADD_MEMBER', 'Invitar miembro al chat'),
    ('UPDATE_MEMBER', 'Actualizar miembro'),
    ('REMOVE_MEMBER', 'Eliminar miembro'),
    ('LEAVE_CHAT', 'Salir del chat'),
    ('UPDATE_MEMBER_ROLE', 'Actualizar rol de miembro'),
    ('LIST_MESSAGES', 'Listar mensajes'),
    ('SEND_MESSAGE', 'Enviar mensaje'),
    ('DELETE_MESSAGE', 'Eliminar mensaje'),
    ('CLEAR_CHAT_HISTORY', 'Limpiar historial del chat'),
    ('MARK_CHAT_AS_READ', 'Marcar chat como leído'),
    ('REGENERATE_AI_RESPONSE', 'Regenerar respuesta IA'),
    ('LIST_BOOKMARKS', 'Listar marcadores'),
    ('BOOKMARK_MESSAGE', 'Marcar/desmarcar mensaje como favorito'),
    ('LIST_PINNED_MESSAGES', 'Listar mensajes fijados'),
    ('PIN_MESSAGE', 'Fijar mensaje'),
    ('SET_MESSAGE_FEEDBACK', 'Feedback sobre mensaje del asistente'),
    ('LIST_THREAD_REPLIES', 'Listar respuestas de hilo'),
    ('ADD_THREAD_REPLY', 'Añadir respuesta en hilo'),
    ('EXPORT_CHAT', 'Exportar chat o mensaje'),
    ('NOTIFICATION_INBOX_LIST', 'Listar bandeja de notificaciones del propio usuario'),
    ('NOTIFICATION_UNREAD_COUNT_GET', 'Consultar contador de notificaciones no leídas'),
    ('NOTIFICATION_STREAM_SUBSCRIBE', 'Suscribirse al stream SSE de notificaciones del propio usuario'),
    ('NOTIFICATION_DETAIL_GET', 'Ver detalle de una notificación propia'),
    ('NOTIFICATION_STATUS_PATCH', 'Marcar notificación propia como leída / no leída / archivada'),
    ('NOTIFICATION_SOFT_DELETE', 'Borrado lógico de una notificación propia'),
    ('NOTIFICATION_MARK_ALL_READ_POST', 'Marcar todas las notificaciones propias como leídas'),
    ('NOTIFICATION_HARD_DELETE', 'Borrado físico de cualquier notificación (admin / mantenimiento)'),
    ('NOTIFICATION_PREFERENCES_GLOBAL_GET', 'Ver preferencias globales de notificación del propio usuario'),
    ('NOTIFICATION_PREFERENCES_GLOBAL_PUT', 'Actualizar preferencias globales de notificación del propio usuario'),
    ('NOTIFICATION_PREFERENCES_EVENT_TYPES_GET', 'Ver matriz de canales por tipo de evento del propio usuario'),
    ('NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT', 'Actualizar canales para un tipo de evento del propio usuario');

INSERT INTO role (name, description) VALUES
    ('superadmin', 'Super administrador con acceso total'),
    ('admin',      'Administrador con acceso de gestión'),
    ('user',       'Usuario estándar del sistema');

INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON TRUE
WHERE r.name = 'superadmin';

INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON TRUE
WHERE r.name = 'admin';

INSERT INTO permission_in_role (role_id, permission_id)
SELECT r.id, p.id
FROM role r
JOIN permission p ON p.name IN (
    'INGEST_DOCUMENT',
    'SOFT_DELETE_DOCUMENTS_BY_CHAT',
    'LIST_CONTEXT_FRAGMENTS_BY_QUESTION',
    'LIST_CONTEXT_FRAGMENTS_BY_DOCUMENTS',
    'GRAPH_QUERY',
    'GRAPH_ENTITY',
    'GRAPH_PATH',
    'LLM_DOCUMENT_QUESTION',
    'LLM_DOCUMENT_QUESTION_STREAM',
    'LLM_DOCUMENT_SUMMARY',
    'LLM_DOCUMENT_ACTION',
    'LLM_AGENT',
    'LLM_DOCUMENT_CLASSIFY',
    'LLM_FRAGMENT_ENRICH',
    'LLM_GRAPH_EXTRACTION',
    'LLM_GRAPH_QUERY_TRANSLATION',
    'GET_USER_AUTHORIZATION',
    'LIST_USER_COMPARTMENTS',
    'GET_USER_ACCESSIBLE_COLLECTIONS',
    'LIST_MY_CHATS',
    'LIST_ARCHIVED_CHATS',
    'CREATE_CHAT',
    'GET_CHAT',
    'UPDATE_CHAT',
    'DELETE_CHAT',
    'PIN_CHAT',
    'ARCHIVE_CHAT',
    'UNARCHIVE_CHAT',
    'LOCK_CHAT',
    'MUTE_CHAT',
    'LIST_SHARE_LINKS',
    'CREATE_SHARE_LINK',
    'DELETE_SHARE_LINK',
    'LIST_WEBHOOKS',
    'CREATE_WEBHOOK',
    'UPDATE_WEBHOOK',
    'DELETE_WEBHOOK',
    'LIST_MEMBERS',
    'ADD_MEMBER',
    'UPDATE_MEMBER',
    'REMOVE_MEMBER',
    'LEAVE_CHAT',
    'UPDATE_MEMBER_ROLE',
    'LIST_MESSAGES',
    'SEND_MESSAGE',
    'DELETE_MESSAGE',
    'CLEAR_CHAT_HISTORY',
    'MARK_CHAT_AS_READ',
    'REGENERATE_AI_RESPONSE',
    'LIST_BOOKMARKS',
    'BOOKMARK_MESSAGE',
    'LIST_PINNED_MESSAGES',
    'PIN_MESSAGE',
    'SET_MESSAGE_FEEDBACK',
    'LIST_THREAD_REPLIES',
    'ADD_THREAD_REPLY',
    'EXPORT_CHAT',
    'NOTIFICATION_INBOX_LIST',
    'NOTIFICATION_UNREAD_COUNT_GET',
    'NOTIFICATION_STREAM_SUBSCRIBE',
    'NOTIFICATION_DETAIL_GET',
    'NOTIFICATION_STATUS_PATCH',
    'NOTIFICATION_SOFT_DELETE',
    'NOTIFICATION_MARK_ALL_READ_POST',
    'NOTIFICATION_PREFERENCES_GLOBAL_GET',
    'NOTIFICATION_PREFERENCES_GLOBAL_PUT',
    'NOTIFICATION_PREFERENCES_EVENT_TYPES_GET',
    'NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT'
)
WHERE r.name = 'user';

INSERT INTO auth_user (
    username, email, password, status,
    account_non_expired, account_non_locked, credentials_non_expired,
    enabled, failed_login_attempts,
    created_by, created_at
) VALUES
    (
        'gral.rodriguez',
        'rodriguez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    ),
    (
        'como.martinez',
        'martinez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    ),
    (
        'cap.gonzalez',
        'gonzalez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    ),
    (
        'ten.lopez',
        'lopez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    ),
    (
        'cabo.perez',
        'perez@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    ),
    (
        'sold.garcia',
        'garcia@faa.mil.ar',
        'pbkdf2_sha256$870000$randomsalt12345$Y1UGqgZ3FpHi7kVEYMijb4XJdANKHDzqOWNBdTN5aEw=',
        'active', true, true, true, true, 0,
        1, NOW()
    );

INSERT INTO auth_user_in_role (auth_user_id, role_id, created_by, created_at) VALUES
    (
        (SELECT id FROM auth_user WHERE username = 'gral.rodriguez'),
        (SELECT id FROM role WHERE name = 'superadmin'),
        1, NOW()
    ),
    (
        (SELECT id FROM auth_user WHERE username = 'como.martinez'),
        (SELECT id FROM role WHERE name = 'admin'),
        1, NOW()
    ),
    (
        (SELECT id FROM auth_user WHERE username = 'cap.gonzalez'),
        (SELECT id FROM role WHERE name = 'admin'),
        1, NOW()
    ),
    (
        (SELECT id FROM auth_user WHERE username = 'ten.lopez'),
        (SELECT id FROM role WHERE name = 'user'),
        1, NOW()
    ),
    (
        (SELECT id FROM auth_user WHERE username = 'cabo.perez'),
        (SELECT id FROM role WHERE name = 'user'),
        1, NOW()
    ),
    (
        (SELECT id FROM auth_user WHERE username = 'sold.garcia'),
        (SELECT id FROM role WHERE name = 'user'),
        1, NOW()
    );
