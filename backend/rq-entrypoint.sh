#!/bin/bash
set -e

# Fix ownership of host-mounted files that may be root-owned from previous runs
TARGET_UID="${WS_DOCKER_UID:-1000}"
TARGET_GID="${WS_DOCKER_GID:-1000}"

chown "$TARGET_UID:$TARGET_GID" /app/ws.log 2>/dev/null || true
chown "$TARGET_UID:$TARGET_GID" /app/shared/imports 2>/dev/null || true

# Drop to host user for all Django operations
exec gosu "$TARGET_UID:$TARGET_GID" bash -c '
set -e

# Run Django migrations
python manage.py migrate

# Run 1 worker for each queue
python manage.py rqworker internal ai email imports --with-scheduler
'
