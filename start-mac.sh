#!/bin/bash
# Start the UV Mix Batch portal on this Mac: http://localhost:8765
# Loads the Pulse DB login from ~/Dev/Pulse/.env, then this folder's .env (portal settings).
cd "$(dirname "$0")"
set -a
source "$HOME/Dev/Pulse/.env"
source ./.env
set +a
pkill -f "uvicorn app.main:app --port 8765" 2>/dev/null && sleep 1
nohup .venv/bin/uvicorn app.main:app --port 8765 > data/server.log 2>&1 &
sleep 2
if curl -s localhost:8765/healthz >/dev/null; then
  echo "UV Mix Batch running: http://localhost:8765  (log: data/server.log)"
  open http://localhost:8765
else
  echo "Did not start - see data/server.log"
fi
