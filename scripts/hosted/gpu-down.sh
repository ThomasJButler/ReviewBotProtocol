#!/usr/bin/env bash
# Point the backend back at the local Ollama, close the tunnel, stop the pod.
# Counterpart of gpu-up.sh; the same caveat applies: not yet exercised
# against RunPod's API when written (2026-09-04).
#
# Usage: gpu-down.sh <pod-id> [local-model]
set -euo pipefail

POD_ID="${1:?pod id}"
LOCAL_MODEL="${2:-qwen3.5:9b}"
LOCAL_PORT="${LOCAL_PORT:-11435}"
ENV_FILE="${ENV_FILE:-$HOME/reviewbot/backend/.env}"
UNIT="${UNIT:-reviewbot-backend}"

sed -i "s#^OLLAMA_BASE_URL=.*#OLLAMA_BASE_URL=http://127.0.0.1:11434#; s#^OLLAMA_MODEL=.*#OLLAMA_MODEL=${LOCAL_MODEL}#" "${ENV_FILE}"
sudo systemctl restart "${UNIT}"
pkill -f "autossh.*-L ${LOCAL_PORT}:127.0.0.1:11434" 2>/dev/null || true
runpodctl stop pod "${POD_ID}"
echo "done: pod ${POD_ID} stopped, backend back on the local ${LOCAL_MODEL}"
