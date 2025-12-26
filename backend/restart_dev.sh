#!/bin/bash

set -euo pipefail

ENV_FILE=".env-docker"

usage() {
  echo "Usage: $0 <service>"
  echo ""
  echo "Services:"
  echo "  backend   Restart Django web server"
  echo "  frontend  Restart frontend dev server"
  echo "  web       Restart backend + frontend"
  echo "  rq        Restart RQ worker"
  echo "  db        Restart PostgreSQL"
  echo "  redis     Restart Redis"
  echo "  all       Restart all services"
  echo ""
  echo "Examples:"
  echo "  $0 backend"
  echo "  $0 web"
  echo "  $0 all"
  exit 1
}

if [ $# -eq 0 ]; then
  usage
fi

case "$1" in
  backend)
    echo "Restarting Django..."
    docker compose --env-file "$ENV_FILE" restart ws-web
    ;;
  rq)
    echo "Restarting RQ worker..."
    docker compose --env-file "$ENV_FILE" restart ws-rq
    ;;
  frontend)
    echo "Restarting frontend..."
    docker compose --env-file "$ENV_FILE" restart ws-frontend
    ;;
  web)
    echo "Restarting backend + frontend..."
    docker compose --env-file "$ENV_FILE" restart ws-frontend
    echo "Waiting for frontend volume sync..."
    sleep 3
    docker compose --env-file "$ENV_FILE" restart ws-web
    ;;
  db)
    echo "Restarting PostgreSQL..."
    docker compose --env-file "$ENV_FILE" restart ws-db
    ;;
  redis)
    echo "Restarting Redis..."
    docker compose --env-file "$ENV_FILE" restart ws-redis
    ;;
  all)
    echo "Restarting all services..."
    docker compose --env-file "$ENV_FILE" restart
    ;;
  *)
    echo "Unknown service: $1"
    usage
    ;;
esac

echo "Done!"
