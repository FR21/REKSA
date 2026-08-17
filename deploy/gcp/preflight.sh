#!/usr/bin/env bash
set -euo pipefail

docker compose config >/dev/null
docker build -t reksa-backend-preflight backend
docker build -t reksa-ai-preflight AI
npm --prefix frontend ci
npm --prefix frontend run build

echo "Local build preflight passed. Cloud credentials were not changed."
