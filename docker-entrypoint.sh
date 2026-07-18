#!/bin/bash
set -e

trap 'kill -TERM $UVICORN_PID $NEXT_PID $CADDY_PID 2>/dev/null' TERM INT

cd /app/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

cd /app/frontend
PORT=3000 HOSTNAME=0.0.0.0 node server.js &
NEXT_PID=$!

caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
CADDY_PID=$!

# If any one of the three dies, exit so the container's restart policy kicks in.
wait -n "$UVICORN_PID" "$NEXT_PID" "$CADDY_PID"
