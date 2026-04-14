-- Migration: normalize role names to lowercase.
-- The init.sql seed already uses lowercase ('superadmin', 'admin', 'user').
-- Run this once on any environment that was seeded before the lowercase convention
-- was enforced, or that had role names stored in a mixed/upper-case form.
--
-- Usage:
--   docker exec -i <auth-db-container> psql -U <user> -d <db> < fix_role_user_lowercase.sql
-- or:
--   psql -h localhost -p 5433 -U <user> -d <db> < fix_role_user_lowercase.sql

UPDATE role SET name = 'superadmin' WHERE name = 'SUPER_ADMIN' OR name = 'SuperAdmin' OR name = 'super_admin';
UPDATE role SET name = 'admin'      WHERE name = 'ADMIN'       OR name = 'Admin';
UPDATE role SET name = 'user'       WHERE name = 'USER'        OR name = 'User';
