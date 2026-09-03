#!/usr/bin/env bash
# Runs inside the container. The container has no network (see prove-local.sh),
# so if this completes, nothing in the review needed the internet.
set -euo pipefail
export OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1 OLLAMA_KEEP_ALIVE=10m OLLAMA_NUM_PARALLEL=1
ollama serve > /tmp/ollama.log 2>&1 &
python3 /app/prove_local/fake_github.py > /tmp/fake-github.log 2>&1 &
for i in $(seq 1 60); do curl -sf http://127.0.0.1:11434/api/tags > /dev/null && break; sleep 1; done
curl -sf http://127.0.0.1:11434/api/tags > /dev/null || { echo "ollama did not start"; cat /tmp/ollama.log; exit 1; }
echo "network interfaces inside the container:"; ip -brief addr 2>/dev/null || cat /proc/net/dev
echo "attempting to reach the internet (must fail):"
if curl -s -m 5 https://api.github.com/ > /dev/null 2>&1; then echo "FAIL: the container can reach the internet, run with --network none"; exit 1; else echo "confirmed: no route out"; fi
cd /app/backend && exec /app/venv/bin/python /app/prove_local/run_proof.py
