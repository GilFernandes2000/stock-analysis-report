#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Building frontend..."
cd "$ROOT/frontend"
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
npm run build

echo "Starting backend on http://localhost:8000"
cd "$ROOT/backend"
if [ -d .venv ]; then
  source .venv/bin/activate
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
