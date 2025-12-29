#!/bin/bash

set -euo pipefail

PORT="${1:-9800}"
PREVIEW_PORT=$((PORT + 1))

export WS_WEB_EXTERNAL_PORT="$PORT"
export WS_PREVIEW_PORT="$PREVIEW_PORT"

WORKTREE_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || echo "default")")
PROJECT_NAME="backend-${WORKTREE_NAME}-${PORT}"

export SOCRATIC_PREVIEW_DIR="${HOME}/tmp/socratic-${PORT}"
mkdir -p "$SOCRATIC_PREVIEW_DIR"

echo "Port: $PORT (preview: $PREVIEW_PORT)"
echo "Project: $PROJECT_NAME"
echo "Preview directory: $SOCRATIC_PREVIEW_DIR"
echo "Starting docker-compose..."

cd "$(dirname "$0")/backend"
docker compose --env-file .env-docker -p "$PROJECT_NAME" up --build
