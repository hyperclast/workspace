#!/bin/bash

set -euo pipefail

ENV_FILE="backend/.env-docker"
WORKTREE_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || echo "default")")

get_running_projects() {
  docker ps --format '{{.Names}}' 2>/dev/null | grep -oE "backend-${WORKTREE_NAME}-[0-9]+" | sort -u
}

usage() {
  echo "Usage: $0 <service> [port]"
  echo ""
  echo "Services:"
  echo "  backend   Restart Django web server"
  echo "  frontend  Restart frontend dev server"
  echo "  web       Restart backend + frontend"
  echo "  rq        Restart RQ worker"
  echo "  db        Restart PostgreSQL"
  echo "  redis     Restart Redis"
  echo "  all       Restart all services (infra first, then app)"
  echo "  ls        List running stacks for this worktree"
  echo ""
  echo "Port:"
  echo "  Optional. If omitted, auto-detects if only one stack is running."
  echo "  Required if multiple stacks are running for this worktree."
  echo ""
  echo "Examples:"
  echo "  $0 backend         # auto-detect port"
  echo "  $0 backend 9800    # explicit port"
  echo "  $0 web 9820"
  echo "  $0 ls              # list running stacks"
  exit 1
}

if [ $# -eq 0 ]; then
  usage
fi

SERVICE="$1"
PORT="${2:-}"

if [ "$SERVICE" = "ls" ]; then
  echo "Running stacks for worktree '$WORKTREE_NAME':"
  PROJECTS=$(get_running_projects)
  if [ -z "$PROJECTS" ]; then
    echo "  (none)"
  else
    echo "$PROJECTS" | while read -r proj; do
      port=$(echo "$proj" | grep -oE '[0-9]+$')
      echo "  - $proj (port $port)"
    done
  fi
  exit 0
fi

if [ -z "$PORT" ]; then
  PROJECTS=$(get_running_projects)
  PROJECT_COUNT=$(echo "$PROJECTS" | grep -c . || echo 0)

  if [ "$PROJECT_COUNT" -eq 0 ]; then
    echo "Error: No running stacks found for worktree '$WORKTREE_NAME'"
    echo "Start one with: ./run-stack.sh [port]"
    exit 1
  elif [ "$PROJECT_COUNT" -eq 1 ]; then
    PROJECT_NAME="$PROJECTS"
    PORT=$(echo "$PROJECT_NAME" | grep -oE '[0-9]+$')
    echo "Auto-detected: $PROJECT_NAME (port $PORT)"
  else
    echo "Error: Multiple stacks running for worktree '$WORKTREE_NAME':"
    echo "$PROJECTS" | while read -r proj; do
      port=$(echo "$proj" | grep -oE '[0-9]+$')
      echo "  - $proj (port $port)"
    done
    echo ""
    echo "Please specify a port: $0 $SERVICE <port>"
    exit 1
  fi
else
  PROJECT_NAME="backend-${WORKTREE_NAME}-${PORT}"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIST="$SCRIPT_DIR/frontend/dist"

cd "$SCRIPT_DIR/backend"

DC="docker compose --env-file .env-docker -p $PROJECT_NAME"

# Wait for a container to report healthy status.
# Usage: wait_healthy <service_name> [timeout_seconds]
wait_healthy() {
  local svc="$1"
  local timeout="${2:-30}"
  local container
  container=$($DC ps -q "$svc" 2>/dev/null)

  if [ -z "$container" ]; then
    echo "  Warning: container for $svc not found, skipping health check"
    return 0
  fi

  # Check if this container has a health check configured
  local has_healthcheck
  has_healthcheck=$(docker inspect --format='{{if .State.Health}}yes{{else}}no{{end}}' "$container" 2>/dev/null || echo "no")
  if [ "$has_healthcheck" = "no" ]; then
    return 0
  fi

  printf "  Waiting for %s to be healthy..." "$svc"
  for i in $(seq 1 "$timeout"); do
    local status
    status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "unknown")
    if [ "$status" = "healthy" ]; then
      echo " ok (${i}s)"
      return 0
    fi
    sleep 1
  done
  echo " timeout after ${timeout}s!"
  echo "  Warning: $svc may not be healthy. Check: docker logs $container"
  return 1
}

rebuild_frontend() {
  echo "Clearing frontend dist for clean rebuild..."
  rm -rf "$FRONTEND_DIST"
  echo "Restarting frontend ($PROJECT_NAME)..."
  $DC restart ws-frontend
  echo "Waiting for frontend rebuild..."
  for i in {1..30}; do
    if [ -f "$FRONTEND_DIST/.vite/manifest.json" ]; then
      echo "Frontend rebuild complete."
      return 0
    fi
    sleep 1
  done
  echo "Warning: Frontend rebuild may not have completed (timeout after 30s)"
}

case "$SERVICE" in
  backend)
    echo "Restarting Django ($PROJECT_NAME)..."
    $DC restart ws-web
    wait_healthy ws-web 30
    ;;
  rq)
    echo "Restarting RQ worker ($PROJECT_NAME)..."
    $DC restart ws-rq
    ;;
  frontend)
    rebuild_frontend
    ;;
  web)
    echo "Restarting backend + frontend ($PROJECT_NAME)..."
    rebuild_frontend
    $DC restart ws-web
    wait_healthy ws-web 30
    ;;
  db)
    echo "Restarting PostgreSQL ($PROJECT_NAME)..."
    $DC restart ws-db
    wait_healthy ws-db 30
    ;;
  redis)
    echo "Restarting Redis ($PROJECT_NAME)..."
    $DC restart ws-redis
    wait_healthy ws-redis 15
    ;;
  all)
    echo "Restarting all services ($PROJECT_NAME)..."
    # Phase 1: Infrastructure (db, redis) — app services depend on these
    echo "Phase 1: Restarting infrastructure..."
    $DC restart ws-db ws-redis
    wait_healthy ws-db 30
    wait_healthy ws-redis 15
    # Phase 2: Frontend rebuild
    echo "Phase 2: Rebuilding frontend..."
    rebuild_frontend
    # Phase 3: App services — now that infra is healthy
    echo "Phase 3: Restarting app services..."
    APP_SERVICES="ws-web ws-rq"
    # Include ws-preview only if it's running (requires --socratic flag)
    if $DC ps --status running 2>/dev/null | grep -q ws-preview; then
      APP_SERVICES="$APP_SERVICES ws-preview"
    fi
    $DC restart $APP_SERVICES
    wait_healthy ws-web 30
    ;;
  *)
    echo "Unknown service: $SERVICE"
    usage
    ;;
esac

echo "Done!"
