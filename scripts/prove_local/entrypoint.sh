#!/usr/bin/env bash
# Runs inside the container. The container has no network (see prove-local.sh),
# so if this completes, nothing in the review needed the internet.
set -euo pipefail
export OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1 OLLAMA_KEEP_ALIVE=10m OLLAMA_NUM_PARALLEL=1
ollama serve > /tmp/ollama.log 2>&1 &
python3 /app/prove_local/fake_github.py > /tmp/fake-github.log 2>&1 &
for i in $(seq 1 60); do curl -sf http://127.0.0.1:11434/api/tags > /dev/null && curl -sf http://127.0.0.1:9999/_posted > /dev/null && break; sleep 1; done
curl -sf http://127.0.0.1:11434/api/tags > /dev/null || { echo "FAIL: ollama did not start"; cat /tmp/ollama.log; exit 1; }
curl -sf http://127.0.0.1:9999/_posted > /dev/null || { echo "FAIL: the fake GitHub server did not start"; cat /tmp/fake-github.log; exit 1; }
echo "interfaces inside the container (must be loopback only):"
ip -brief addr 2>/dev/null | tee /tmp/ifaces || cat /proc/net/dev
# Docker's kernel exposes DOWN tunnel stubs (tunl0, sit0, gre0) with no address; only an interface that is up or addressed is a way out.
if ip -brief addr 2>/dev/null | awk '$1 !~ /^lo/ && ($2 != "DOWN" || NF > 2)' | grep -q .; then echo "FAIL: a non-loopback interface is up or addressed; run with --network none"; exit 1; fi
echo "raw connect to 1.1.1.1:443 with no DNS involved (must fail):"
if /app/venv/bin/python - <<'PY'
import socket, sys
s = socket.socket(); s.settimeout(3)
try:
    s.connect(("1.1.1.1", 443)); sys.exit(0)
except OSError as e:
    print("connect failed as expected:", type(e).__name__); sys.exit(1)
PY
then echo "FAIL: the container has a route to the internet"; exit 1; else echo "confirmed: no route out"; fi
echo "model in use:"; model_info=$(ollama show "${OLLAMA_MODEL}" 2>/dev/null || true); printf '%s\n' "${model_info}" | head -12
echo "python packages in the proof image:"; packages=$(/app/venv/bin/pip freeze 2>/dev/null || true); printf '%s\n' "${packages}" | tr '\n' ' '; echo
cd /app/backend && exec /app/venv/bin/python /app/prove_local/run_proof.py
