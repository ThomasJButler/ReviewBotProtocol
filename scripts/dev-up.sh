#!/usr/bin/env bash
# Start the tunnel, the backend and the dashboard together for a hands-on run.
# The backend runs in the foreground so its log is on screen; ngrok and the
# dashboard log to .dev-logs/. Ctrl-C stops all three.
#
#   NGROK_DOMAIN=<name>.ngrok-free.dev scripts/dev-up.sh
#
# Needs: backend/.env filled in, backend/.venv installed, .env.local for the
# dashboard, ngrok logged in (ngrok config add-authtoken ...), Ollama running.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="${NGROK_DOMAIN:-${1:-}}"
if [ -z "$DOMAIN" ]; then
  echo "usage: NGROK_DOMAIN=<your static ngrok domain> $0" >&2
  exit 1
fi
for need in "$ROOT/backend/.env" "$ROOT/backend/.venv/bin/uvicorn" "$ROOT/.env.local"; do
  [ -e "$need" ] || { echo "missing $need" >&2; exit 1; }
done
command -v ngrok >/dev/null || { echo "ngrok is not installed (brew install ngrok)" >&2; exit 1; }

LOGS="$ROOT/.dev-logs"
mkdir -p "$LOGS"
trap 'kill 0 2>/dev/null' INT TERM EXIT

ngrok http --url="$DOMAIN" 8000 --log=stdout > "$LOGS/ngrok.log" 2>&1 &
(cd "$ROOT" && npm run dev) > "$LOGS/dashboard.log" 2>&1 &
sleep 2
echo "tunnel     https://$DOMAIN/webhook/github   (inspector http://127.0.0.1:4040)"
echo "backend    http://127.0.0.1:8000"
echo "dashboard  http://127.0.0.1:3000/status"
echo "logs       $LOGS/ngrok.log, $LOGS/dashboard.log; the backend logs here. Ctrl-C stops all three."
cd "$ROOT/backend"
exec .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
