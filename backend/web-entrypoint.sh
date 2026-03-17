#!/bin/bash
set -e

# Fix ownership of host-mounted files that may be root-owned from previous runs
TARGET_UID="${WS_DOCKER_UID:-1000}"
TARGET_GID="${WS_DOCKER_GID:-1000}"

chown "$TARGET_UID:$TARGET_GID" /app/ws.log 2>/dev/null || true
chown -R "$TARGET_UID:$TARGET_GID" /app/static 2>/dev/null || true
chown "$TARGET_UID:$TARGET_GID" /app/shared/imports 2>/dev/null || true

# Drop to host user for all Django operations
exec gosu "$TARGET_UID:$TARGET_GID" bash -c '
set -e

# Auto-generate missing migrations (if any)
if ! python manage.py makemigrations --check --dry-run 2>/dev/null; then
    echo ""
    echo "WARNING: Missing migrations detected. Auto-generating..."
    python manage.py makemigrations
    echo ""
    echo "NOTE: Migrations were auto-generated. Please review them and add to version control."
    echo ""
fi

# Run Django migrations
python manage.py migrate

# Run collectstatic
python manage.py collectstatic --no-input

# Start Uvicorn directly for development
PORT="${WS_WEB_INTERNAL_PORT:-9800}"
exec uvicorn backend.asgi:application \
    --host 0.0.0.0 \
    --port ${PORT} \
    --reload \
    --reload-include "*.html" \
    --reload-exclude "__pycache__"
'
