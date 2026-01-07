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

# Auto-copy .env-docker from main worktree if missing (common in new worktrees)
if [[ ! -f .env-docker ]]; then
    MAIN_WORKTREE=$(git worktree list --porcelain | grep -m1 '^worktree ' | cut -d' ' -f2-)
    if [[ -f "$MAIN_WORKTREE/backend/.env-docker" ]]; then
        echo "Copying .env-docker from main worktree..."
        cp "$MAIN_WORKTREE/backend/.env-docker" .env-docker
    else
        echo "Error: .env-docker not found. Copy from backend/.env-template or another worktree."
        exit 1
    fi
fi

# --pull missing: only pull images if not cached (enables offline dev)
docker compose --env-file .env-docker -p "$PROJECT_NAME" up --build --pull missing
