# ReviewBot Protocol

A GitHub App that reviews pull requests with a language model running on your own machine, and a small local dashboard to see what it said. Nothing about the code you review is sent to a model provider. During a review the only network peer is api.github.com, and there is a test that fails if that stops being true.

Built by Tom Butler as a demonstration of private, local AI: AI you own rather than AI you rent. It started as a Codecademy bootcamp project on OpenAI and was rebuilt in September 2026 to run entirely on Ollama, after a security review of the original (see docs/SECURITY_REVIEW.md, which is unsparing).

## What it does

1. You install the App on selected repositories. When a pull request is opened, pushed to, reopened or marked ready for review, GitHub sends a webhook to the backend.
2. The backend verifies the signature, ignores replays, and queues one review per PR head. A single worker fetches the changed files with an installation token.
3. Secret-bearing files are skipped outright. Every other patch is redacted (API keys, tokens, private keys, passwords) before a model sees it.
4. One structured call per file to a local Ollama model. The diff is inside a delimited data block the model is told is untrusted; the answer must fit a fixed JSON schema; findings that quote lines not in the diff are dropped.
5. One review is posted to the PR (a comment review, never an approval), sanitised so the model cannot inject HTML, off-site links or mentions, with a footer naming the model.
6. The dashboard shows what was reviewed, what was said, and lets you mark each review useful or not.

## What it deliberately does not do

- It never approves, requests changes, or sets commit statuses. Nothing the model says can gate a merge.
- It has no cloud fallback. If Ollama is down, reviews fail visibly and are recorded as failed.
- It has no manual paste-your-code mode, no GitHub OAuth, no multi-user anything. It is a tool for one person's repositories.
- It is not a product. It is well tested for what it does, and it has been run end to end on real pull requests by exactly one person.

## Privacy, stated precisely

Leaves the machine: HTTPS requests to api.github.com to read the PR, its files, and post the review. That is the complete list.

Never leaves the machine: the diff, the prompt, the model's output. The backend refuses to start if the environment contains a LangSmith tracing flag or an OpenAI, Anthropic, Google, Mistral or Sentry key (`STRICT_LOCAL`, on by default). No telemetry, no analytics, no fonts or scripts from a CDN in the dashboard. Next.js telemetry is disabled in the scripts.

Stored on your disk (SQLite): repository, PR number and title, head SHA, model, timings, token counts, the skipped files, the posted review body, and each finding. Patches are not stored. Logs never contain diffs or model output unless you set `LOG_PROMPTS=true`.

Ollama: bound to loopback. The desktop app checks ollama.com hourly for updates of itself (never prompt content); run `ollama serve` from a terminal with `OLLAMA_NO_CLOUD=1` if you want no outbound connection at all.

### The proof

Three checks, all in the repository:

- `backend/tests/test_runner.py` runs a whole review through the real code against a fake GitHub API and a fake model with a socket-level guard that blocks every host except loopback. It runs in CI.
- `REVIEWBOT_E2E=1 pytest -m e2e` does the same with the real Ollama and model on your machine.
- `scripts/prove-local.sh` builds a container with the backend, Ollama and a small model, then runs one review with `docker run --network none`. The entrypoint first proves the container cannot reach the internet. Last run: 2026-09-03, passed.

## Quick start

You need Python 3.13, Node 22, Ollama, and a GitHub App you own.

Backend:

```
cd backend
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env      # GitHub App id, private key path, webhook secret, and a LOCAL_API_TOKEN
ollama pull qwen3.5:9b
.venv/bin/python main.py  # 127.0.0.1:8000
```

Dashboard:

```
npm install
cp .env.example .env.local   # BACKEND_URL and the same LOCAL_API_TOKEN
npm run dev                   # http://localhost:3000
```

Expose only `POST /webhook/github` on the backend to the internet (a tunnel or a reverse proxy), add that hostname to `ALLOWED_HOSTS`, and point the App's webhook at it. The full App setup, permissions (Pull requests read and write, Metadata read, nothing else) and all settings are in backend/README.md and on the dashboard's Setup page.

## Choosing a model

The honest trade-off: a local model is not GPT-4o, and a small one is a triage layer, not an unattended reviewer.

| Model | Disk | On an M1 Max 32 GB | What to expect |
|---|---|---|---|
| `qwen3.5:9b` | 6.6 GB | about 33 tokens per second, fully on GPU | catches obvious injection, hard-coded secrets and clear bugs; misses subtle logic; can over-report style |
| `qwen3-coder:30b` | 19 GB | mixture-of-experts, 45 to 60 tokens per second estimated | the recommended primary when you have the disk; needs `OLLAMA_NUM_CTX=16384` on 32 GB |
| `qwen3.6:27b` | 17 GB | dense, 12 to 16 tokens per second estimated | strongest on benchmarks; slow enough that a 20-file PR takes a while |

Vendor benchmark numbers and the reasoning behind these picks are in docs/LOCAL_MIGRATION.md. Findings are checked against the diff before posting, which removes most of what a small model invents; it does not make a small model clever.

## Repository layout

```
backend/     FastAPI service: webhook, queue, redaction, review pipeline, dashboard API, tests
app/ components/ lib/   Next.js dashboard (four screens: reviews, review detail, status, setup)
docs/        SECURITY_REVIEW.md (91 findings and their status), LOCAL_MIGRATION.md (design), FRONTEND_PLAN.md
scripts/     prove-local.sh and the container proof
.github/     CI (tests, lint, types, build, audits) and Dependabot
```

## Licence

MIT.
