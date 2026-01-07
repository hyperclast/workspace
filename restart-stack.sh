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
  echo "  all       Restart all services"
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

cd "$(dirname "$0")/backend"

DC="docker compose --env-file .env-docker -p $PROJECT_NAME"

case "$SERVICE" in
  backend)
    echo "Restarting Django ($PROJECT_NAME)..."
    $DC restart ws-web
    ;;
  rq)
    echo "Restarting RQ worker ($PROJECT_NAME)..."
    $DC restart ws-rq
    ;;
  frontend)
    echo "Restarting frontend ($PROJECT_NAME)..."
    $DC restart ws-frontend
    ;;
  web)
    echo "Restarting backend + frontend ($PROJECT_NAME)..."
    $DC restart ws-frontend
    echo "Waiting for frontend volume sync..."
    sleep 3
    $DC restart ws-web
    ;;
  db)
    echo "Restarting PostgreSQL ($PROJECT_NAME)..."
    $DC restart ws-db
    ;;
  redis)
    echo "Restarting Redis ($PROJECT_NAME)..."
    $DC restart ws-redis
    ;;
  all)
    echo "Restarting all services ($PROJECT_NAME)..."
    $DC restart
    ;;
  *)
    echo "Unknown service: $SERVICE"
    usage
    ;;
esac

echo "Done!"
