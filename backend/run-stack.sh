#!/bin/bash

set -euo pipefail

# Create socratic preview directory
export SOCRATIC_PREVIEW_DIR="${HOME}/tmp/socratic"
mkdir -p "$SOCRATIC_PREVIEW_DIR"
echo "Preview directory: $SOCRATIC_PREVIEW_DIR"

echo "Now running docker-compose..."

docker compose --env-file .env-docker up --build
