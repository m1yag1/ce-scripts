#!/usr/bin/env bash

set -euxo pipefail

: "${HOST:?'SSH host required (example: ssh://swarm-worker-prod-1)'}"
: "${CONTAINER:?'Container id required'}"

docker -H "$HOST" cp ./abl_migration.py $CONTAINER:/app/abl_migration.py
docker -H "$HOST" exec -t -e GITHUB_TOKEN="$GITHUB_TOKEN" $CONTAINER /bin/bash -ce '
    python /app/abl_migration.py && \
    rm /app/abl_migration.py'
