#!/bin/sh
# Container entrypoint for aura-auth-service.
#
# Runs the idempotent seeding of the downstream *_MANAGE permissions before
# starting the web server, so a fresh deploy has the permissions the admin
# panel needs to call document-processing's manage endpoints. The step is
# non-fatal: if it fails (e.g. the DB is not migrated yet) the web server still
# starts, and the seed can be re-run later with:
#   docker exec aura-auth-service python manage.py seed_service_manage_permissions --execute
set -e

echo "[entrypoint] running database migrations..."
python manage.py migrate

echo "[entrypoint] seeding service manage permissions (idempotent)..."
python manage.py seed_service_manage_permissions --execute || \
  echo "[entrypoint] seed skipped/failed (non-fatal); continuing startup"

exec "$@"
