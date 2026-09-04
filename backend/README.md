# ReviewBot Protocol backend

A FastAPI service that receives GitHub pull request webhooks, reviews the diff with a model running locally in Ollama, and posts the review back to the pull request as one review comment with inline notes. No inference API key exists anywhere in its configuration; in local mode, the default, the only network peer during a review is api.github.com. The same service runs unchanged on a rented server for a bigger model (hosted mode step A in docs/HOSTED_MODEL_PLAN.md), where the sentences below about the machine describe that server; in step B the model sits on a rented GPU reached over an SSH tunnel, so the diff does leave the server, over SSH, to hardware rented by the hour.

## What it does, precisely

1. GitHub sends a `pull_request` webhook (opened, synchronize, reopened, ready_for_review). The body is capped, the HMAC-SHA256 signature is verified over the raw bytes, the delivery id is recorded (a repeat is ignored), and the request returns 202. Nothing slow happens in the request.
2. A single worker takes the job. A head SHA that is queued, in flight or already reviewed to completion is not reviewed again; a newer push replaces a waiting job or cancels the one in flight; every job has a deadline. One backend per database: a second instance refuses to start.
3. It fetches the PR and its changed files with a GitHub App installation token. Deleted, binary, generated, vendored, non-code and oversized files are skipped, and so is anything secret-bearing by name (`.env`, `*.pem`, `id_rsa`, `*.tfvars` and so on).
4. Every patch is redacted (API keys, tokens, private keys, passwords in URLs and assignments) before it reaches the model, the posted comment, the log or the database.
5. One structured model call per file, with the model prompted as a specialist security reviewer: the diff goes inside a delimited data block that the system prompt declares untrusted (text in the diff addressed to a reviewer is reported as a prompt-injection attempt, never obeyed), and the model must answer with JSON matching a fixed schema. Findings are then dropped unless the quoted evidence really is in the diff and confidence clears a floor. With `VERIFY_FINDINGS=true` each surviving finding gets a second call whose only job is to disprove it; severity can only go down. `scripts/prompt_eval.py` measures all of this against the real model.
6. The findings are rendered as one pull request review (event COMMENT, never approve or request changes), sanitised (no HTML, links only to github.com, mentions neutralised, bounded length), with a footer naming the model. Fork PRs are reviewed the same way and labelled.
7. The review, its findings and timing are stored in SQLite for the dashboard. Patches are not stored.

## Requirements

- Python 3.13 (3.11 and 3.12 should work; 3.14 does not have wheels for every dependency yet)
- Ollama on the same machine as the backend (loopback), with a model pulled (`ollama pull qwen3.5:9b` to start; see Models)
- A GitHub App you own (see below)

## Setup

```
cd backend
python3.13 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements.lock
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env    # fill in GITHUB_APP_ID, GITHUB_PRIVATE_KEY, GITHUB_WEBHOOK_SECRET, LOCAL_API_TOKEN
.venv/bin/python main.py
```

The service binds 127.0.0.1:8000 by default. To receive webhooks you expose `POST /webhook/github` through a tunnel or a reverse proxy and add that hostname to `ALLOWED_HOSTS`. Do not expose anything else; the dashboard API under `/api` is meant for the local frontend only.

### GitHub App

Create a GitHub App (Settings, Developer settings, GitHub Apps, New GitHub App):

- Webhook URL: your public URL for `/webhook/github`. Webhook secret: a long random value (`openssl rand -hex 32`), the same one you put in `.env`.
- Repository permissions: Pull requests, Read and write. Metadata, Read. Nothing else.
- Subscribe to events: Pull request. Nothing else.
- Generate a private key and point `GITHUB_PRIVATE_KEY` at the downloaded `.pem`. Keep the file outside the repository; `.gitignore` and `.dockerignore` exclude `*.pem` as a backstop.
- Install the App on selected repositories, never on all repositories.

A `ping` event arrives when the webhook is saved; it is answered with `{"status": "pong"}` and recorded under `/api/deliveries` with status `pong`. Every signed delivery is recorded, including ignored events and skipped drafts, so the Status page shows what GitHub sent.

## Models

Set `OLLAMA_MODEL`. Any Ollama chat model works; these were assessed for this job on an Apple M1 Max with 32 GB:

| Model | Disk | Notes |
|---|---|---|
| `qwen3.5:9b` | 6.6 GB | fast (about 33 tokens per second, one observation), and on the eleven planted diffs in `tests/prompt_corpus.py` it found every planted bug at the right line, reported the planted instruction both times, and flagged nothing on the clean diffs (2026-09-04, two repeats, `scripts/prompt_eval.py`); still a triage layer rather than an unattended reviewer on real code |
| `qwen3-coder:30b` | 19 GB | mixture-of-experts coder, the recommended primary when disk allows; run with `OLLAMA_NUM_CTX=16384` |
| `qwen3.6:27b` | 17 GB | dense, thinking-capable, slower (12 to 16 tokens per second estimated, not measured) |

Thinking is switched off for the review call; the output is constrained to the JSON schema by Ollama's `format` parameter. Keep `OLLAMA_NUM_CTX` constant for a model, because changing it reloads the model.

Recommended Ollama server settings on the host: `OLLAMA_NO_CLOUD=1` (disables Ollama's cloud inference and web search), `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_MAX_LOADED_MODELS=1`, and leave `OLLAMA_HOST` unset so it stays on loopback. Run `ollama serve` from a terminal or a service rather than the desktop app if you want no update checks at all (the app polls ollama.com hourly for its own updates; no prompt content is sent). Never set `OLLAMA_MODEL` to a cloud-hosted tag (`-cloud` suffix): a local Ollama would relay every prompt to ollama.com and nothing in this backend could tell. `STRICT_LOCAL` rejects such a tag at startup.

## What leaves the machine, and what is stored

Leaves the machine (local mode; in hosted mode read "the server"): requests to `api.github.com` only (fetch the PR and its files, post the review). Nothing is sent to any model provider, error tracker or tracing service, and the process refuses to start if the environment says otherwise (`STRICT_LOCAL`, on by default, fails on `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGCHAIN_API_KEY`, `LANGSMITH_API_KEY`, `SENTRY_DSN` and on any LangSmith tracing variable set to true).

Stored locally in `reviews.db`: repository, PR number and title, head SHA, model, timings and token counts, the skipped files with reasons, the posted review body, and each finding (path, line, severity, title, quoted evidence, recommendation, confidence). Patches are not stored. Logs go to stdout and never contain diffs, prompts or model output unless `LOG_PROMPTS=true`.

## Proving it

- `.venv/bin/python -m pytest` runs the suite, including whole reviews through the real code with a fake GitHub API answered in-process and a fake model, under a socket-level guard that fails the test if anything in the process connects or resolves a name outside loopback.
- `REVIEWBOT_E2E=1 .venv/bin/python -m pytest -m e2e` reviews one diff with the real Ollama and model under the same guard. Skipped by default.
- Manual capture: run `lsof -i -P -a -p $(pgrep -f 'uvicorn main:app')` in a second terminal every second while a real PR is reviewed. The only peers you should ever see are `127.0.0.1:11434` (Ollama) and `api.github.com:443`.
- `../scripts/prove-local.sh` builds a container holding the backend, Ollama and a small model, then runs one review with `docker run --network none`.

## Measuring the prompt

`scripts/prompt_eval.py` runs eleven small planted diffs (SQL injection, hard-coded key, eval, path traversal, shell=True, MD5 passwords, a missing auth check, a planted instruction next to a command injection, a check-then-act race, and two clean diffs) through the real reviewer against the live Ollama, for the old prompt, the current one, and the current one with the verify pass, and prints recall, drop reasons, false positives, whether the planted instruction was obeyed, tokens and seconds. On qwen3.5:9b on 2026-09-04 (two repeats each): old prompt recall 0.89 with the instruction reported once; current prompt recall 1.0, instruction reported twice, no false positives, about 960 tokens and 8 seconds per file; with the verify pass recall 0.78, because the 9B refuted real findings while there were no false positives left to remove. That is why `VERIFY_FINDINGS` is off by default; measure again on a bigger model before turning it on. A separate red-team set of fifteen hostile diffs (forged audit notes, fake scanner output, exfiltration requests, forged delimiters, bidi characters, a nested fake diff, each beside a real bug) was obeyed 0 times out of 15 and leaked nothing into the posted text, with the real bug found in 14 of 15. `REVIEWBOT_PROMPT_EVAL=1 .venv/bin/python -m pytest -m prompt_eval` is the same corpus as a pass or fail floor.

## Limits

`MAX_FILES_PER_REVIEW` (25), `MAX_PATCH_BYTES` (32 000, which must fit `OLLAMA_NUM_CTX`), `MAX_WEBHOOK_BODY_BYTES` (2 MiB), `MAX_INLINE_COMMENTS` (25), `REVIEW_TIMEOUT_SECONDS` (900), `MIN_FINDING_CONFIDENCE` (0.5). Draft PRs are skipped unless `REVIEW_DRAFTS=true`.

## API for the dashboard

All routes need `Authorization: Bearer <LOCAL_API_TOKEN>`. With no token configured they answer 503.

- `GET /api/reviews?repository=&limit=&offset=`
- `GET /api/reviews/{id}`
- `POST /api/reviews/{id}/feedback` with `{"useful": true | false | null}`
- `GET /api/deliveries?limit=`
- `GET /api/status` (Ollama reachability and loaded models, queue depth, database, limits)

`GET /health` is public and returns only `{"status": "ok", "version": ...}`.

## Layout

```
backend/
  main.py                 app, middleware, lifespan (starts the queue)
  config/settings.py      all settings and the local-only guard
  handlers/webhook.py     the public route
  handlers/review.py      the dashboard API
  services/               redaction, diff parsing, prompt, schema, reviewer, renderer, queue, workflow, runner, GitHub client
  database/               SQLAlchemy models and repositories
  tests/                  pytest suite
```
