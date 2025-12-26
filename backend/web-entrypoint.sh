#!/bin/bash
set -e

# Run Django migrations
python manage.py migrate

# Run collectstatic
python manage.py collectstatic --no-input

# Start Uvicorn directly for development
# - Use --reload to auto-restart on code changes
# - Use --reload-include to also watch template files
PORT="${WS_WEB_INTERNAL_PORT:-9800}"
exec uvicorn backend.asgi:application \
    --host 0.0.0.0 \
    --port ${PORT} \
    --reload \
    --reload-include "*.html"
