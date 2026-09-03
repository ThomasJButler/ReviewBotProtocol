#!/usr/bin/env bash
# Proves the review pipeline needs no network: builds an image containing the
# backend, Ollama and a small model, then runs one full review inside it with
# networking disabled entirely. Exit code is the verdict.
#
#   ./scripts/prove-local.sh            # build (first time is slow) and run
#   MODEL=qwen3.5:9b ./scripts/prove-local.sh   # use a bigger model (slower on CPU)
set -euo pipefail
cd "$(dirname "$0")/.."
MODEL="${MODEL:-qwen3.5:0.8b}"
IMAGE="reviewbot-prove-local:${MODEL//[:\/]/-}"
echo "building ${IMAGE} (downloads the model once)"
docker build -f Dockerfile.local --build-arg MODEL="${MODEL}" -t "${IMAGE}" .
echo "running one review with --network none"
docker run --rm --network none -e OLLAMA_MODEL="${MODEL}" "${IMAGE}"
echo "PASS: a full review completed with no network available"
