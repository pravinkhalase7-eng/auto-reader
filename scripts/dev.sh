#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting API on :8000..."
cd "$ROOT/apps/api"
# shellcheck disable=SC1091
source .venv/bin/activate
SEED_ON_STARTUP=true uvicorn app.main:app --reload --port 8000 &
API_PID=$!

echo "Starting Web on :3000..."
cd "$ROOT/apps/web"
npm run dev &
WEB_PID=$!

trap 'kill $API_PID $WEB_PID 2>/dev/null || true' EXIT
wait
