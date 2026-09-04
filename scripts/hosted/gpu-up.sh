#!/usr/bin/env bash
# Start the RunPod GPU pod that holds Ollama and qwen3-coder:30b, open an SSH
# tunnel to it on 127.0.0.1:11435, wait for the model, and restart the
# backend pointed at the tunnel. Reverse with gpu-down.sh.
#
# NOT YET EXERCISED against RunPod's API when written (2026-09-04); read
# docs/HOSTED_MODEL_PLAN.md step B1 and check each command against the
# current runpodctl help before relying on it.
#
# Usage: gpu-up.sh <pod-id> <ssh-host> <ssh-port> [model]
set -euo pipefail

POD_ID="${1:?pod id}"
SSH_HOST="${2:?ssh host}"
SSH_PORT="${3:?ssh port}"
MODEL="${4:-qwen3-coder:30b}"
LOCAL_PORT="${LOCAL_PORT:-11435}"
ENV_FILE="${ENV_FILE:-$HOME/reviewbot/backend/.env}"
UNIT="${UNIT:-reviewbot-backend}"

command -v runpodctl >/dev/null || { echo "runpodctl is not installed"; exit 1; }
command -v autossh >/dev/null || { echo "autossh is not installed (apt install autossh)"; exit 1; }
[[ "${MODEL}" =~ ^[A-Za-z0-9._:/-]+$ ]] || { echo "model tag has characters this script will not put in .env"; exit 1; }
[[ "${LOCAL_PORT}" =~ ^[0-9]+$ ]] && [[ "${SSH_PORT}" =~ ^[0-9]+$ ]] || { echo "ports must be numbers"; exit 1; }
[[ "${SSH_HOST}" =~ ^[A-Za-z0-9.-]+$ ]] || { echo "ssh host has characters this script will not use"; exit 1; }
[ -f "${ENV_FILE}" ] || { echo "no ${ENV_FILE}; set ENV_FILE"; exit 1; }
sudo -n true 2>/dev/null || { echo "needs passwordless sudo for: systemctl restart ${UNIT} (see docs/HOSTED_MODEL_PLAN.md B1)"; exit 1; }

echo "starting pod ${POD_ID}"
runpodctl start pod "${POD_ID}"

echo "waiting for ssh on ${SSH_HOST}:${SSH_PORT}"
ssh_ok=0
for _ in $(seq 1 60); do
  if ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new -p "${SSH_PORT}" "root@${SSH_HOST}" true 2>/dev/null; then
    ssh_ok=1
    break
  fi
  sleep 5
done
if [ "${ssh_ok}" != 1 ]; then
  echo "ssh never answered on ${SSH_HOST}:${SSH_PORT}; check the pod's Connect panel for a new host or port. Stopping the pod so it does not bill."
  runpodctl stop pod "${POD_ID}" || true
  exit 1
fi

echo "opening the tunnel on 127.0.0.1:${LOCAL_PORT}"
pkill -f "autossh.*-L ${LOCAL_PORT}:127.0.0.1:11434" 2>/dev/null || true
AUTOSSH_GATETIME=0 autossh -M 0 -f -N -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -L "${LOCAL_PORT}:127.0.0.1:11434" -p "${SSH_PORT}" "root@${SSH_HOST}"

echo "waiting for ${MODEL} on the pod"
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${LOCAL_PORT}/api/tags" | grep -q "\"${MODEL}\""; then
    break
  fi
  sleep 5
done
if ! curl -sf "http://127.0.0.1:${LOCAL_PORT}/api/tags" | grep -q "\"${MODEL}\""; then
  echo "the model is not on the pod; run: ollama pull ${MODEL} there. Closing the tunnel and stopping the pod."
  pkill -f "autossh.*-L ${LOCAL_PORT}:127.0.0.1:11434" 2>/dev/null || true
  runpodctl stop pod "${POD_ID}" || true
  exit 1
fi

echo "pointing the backend at the tunnel"
sed -i "s#^OLLAMA_BASE_URL=.*#OLLAMA_BASE_URL=http://127.0.0.1:${LOCAL_PORT}#; s#^OLLAMA_MODEL=.*#OLLAMA_MODEL=${MODEL}#" "${ENV_FILE}"
sudo systemctl restart "${UNIT}"
echo "done: the backend reviews with ${MODEL} on the pod; remember gpu-down.sh when finished"
