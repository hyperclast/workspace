#!/bin/bash

set -euo pipefail

# Parse arguments
USE_MINIO=false
USE_SOCRATIC=false
PORT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --minio)
            USE_MINIO=true
            shift
            ;;
        --socratic)
            USE_SOCRATIC=true
            shift
            ;;
        *)
            PORT="$1"
            shift
            ;;
    esac
done

PORT="${PORT:-9800}"

export WS_WEB_EXTERNAL_PORT="$PORT"

WORKTREE_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || echo "default")")
PROJECT_NAME="backend-${WORKTREE_NAME}-${PORT}"

echo "Port: $PORT"
echo "Project: $PROJECT_NAME"

if [[ "$USE_SOCRATIC" == "true" ]]; then
    PREVIEW_PORT=$((PORT + 1))
    export WS_PREVIEW_PORT="$PREVIEW_PORT"
    export SOCRATIC_PREVIEW_DIR="${HOME}/tmp/socratic-${PORT}"
    mkdir -p "$SOCRATIC_PREVIEW_DIR"
    echo "Socratic: enabled (preview on $PREVIEW_PORT, dir: $SOCRATIC_PREVIEW_DIR)"
fi

if [[ "$USE_MINIO" == "true" ]]; then
    echo "MinIO: enabled (S3 API on 9000, console on 9001)"
fi

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

# Build compose command
# --pull missing: only pull images if not cached (enables offline dev)
# Override files are additive — each adds services/config on top of the base
COMPOSE_CMD="docker compose --env-file .env-docker"

if [[ "$USE_SOCRATIC" == "true" || "$USE_MINIO" == "true" ]]; then
    COMPOSE_CMD="$COMPOSE_CMD -f docker-compose.yaml"
    [[ "$USE_SOCRATIC" == "true" ]] && COMPOSE_CMD="$COMPOSE_CMD -f docker-compose.socratic.yaml"
    [[ "$USE_MINIO" == "true" ]] && COMPOSE_CMD="$COMPOSE_CMD -f docker-compose.minio.yaml"
fi

COMPOSE_CMD="$COMPOSE_CMD -p $PROJECT_NAME up --build --pull missing"

$COMPOSE_CMD
