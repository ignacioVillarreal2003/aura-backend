DELETE FROM django_migrations WHERE app IN ('auth', 'contenttypes');

INSERT INTO django_migrations (app, name, applied) 
VALUES 
    ('auth', '0001_initial', '2026-01-26 12:36:00'::timestamp),
    ('auth', '0002_alter_permission_options', '2026-01-26 12:36:00'::timestamp),
    ('auth', '0003_alter_user_email_max_length', '2026-01-26 12:36:00'::timestamp),
    ('auth', '0004_alter_user_username_opts', '2026-01-26 12:36:00'::timestamp),
    ('auth', '0005_alter_user_last_login_null', '2026-01-26 12:36:00'::timestamp),
    ('auth', '0006_require_contenttypes_0002', '2026-01-26 12:36:00'::timestamp),
    ('auth', '0007_alter_validators_add_error_messages', '2026-01-26 12:36:00'::timestamp),
    ('auth', '0008_alter_user_username_max_length', '2026-01-26 12:36:00'::timestamp),
    ('auth', '0009_alter_user_last_name_max_length', '2026-01-26 12:36:00'::timestamp),
    ('auth', '0010_alter_group_name_max_length', '2026-01-26 12:36:00'::timestamp),
    ('auth', '0011_update_proxy_permissions', '2026-01-26 12:36:00'::timestamp),
    ('auth', '0012_alter_user_first_name_max_length', '2026-01-26 12:36:00'::timestamp),
    ('contenttypes', '0001_initial', '2026-01-26 12:36:00'::timestamp),
    ('contenttypes', '0002_remove_content_type_name', '2026-01-26 12:36:00'::timestamp);
