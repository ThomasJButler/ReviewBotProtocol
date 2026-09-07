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
| `qwen3.5:9b` | 6.6 GB | fast (about 33 tokens per second, one observation); with the shipped prompt on the 91-case corpus in `tests/` it finds the planted problem in 95 percent of diffs at 0.19 false positives per clean diff and obeys none of the 32 planted instructions (2026-09-06, two repeats, docs/benchmarks/); still a triage layer rather than an unattended reviewer on real code |
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

## The cross-examiner: a second model from a different family

Set `CROSS_EXAMINE_MODEL` to a second Ollama model tag (for example `gemma4:12b`, a Google model beside the Qwen reviewer) and every file's review gets a second opinion in one extra call: the cross-examiner sees the diff and the first reviewer's numbered findings inside the same delimited data block, judges each one real or a false positive with the decisive line and a severity no higher than claimed, adds what the first reviewer missed under the same evidence rules, and writes a one-line note on where the two disagree. Reconciliation is one pass with no debate: a refutation only counts when the cross-examiner's confidence clears `MIN_FINDING_CONFIDENCE`, severity can only go down, additions must quote a line that is really in the diff, and anything unreadable leaves the first review unchanged. Every finding records which model raised it and what the other said (`source_model`, `cross_verdict`, `cross_reason`), the posted review names both models and marks additions and disagreements, and the dashboard shows the same. The reasoning, with the evidence, is in docs/PROMPT_DESIGN.md: models tend not to see their own family's mistakes, so a reviewing pair should be diverse from each other and from the model that wrote the code. One reconciliation rule learned from measuring `gemma4:12b`: when it answers false positive and then adds the same problem in its own words on the same line, it is correcting the severity, not refuting, so the first reviewer's finding stands at the lowest severity anyone gave it, with the reason recorded. `CROSS_EXAMINE_MAX_CALLS_PER_REVIEW` (25) bounds the cost. Both models talk to the same loopback Ollama, so the local claim is unchanged. A 9B and a 12B resident together need about 15 GB, which is more than a 32 GB laptop can spare beside everything else (the first measurement night ended with macOS killing the jobs); on such a machine set `CROSS_EXAMINE_SEQUENTIAL=true` and the review runs one model at a time, reviewing every file with the first model, asking Ollama to unload it, cross-examining every file with the second, and unloading that, with the per-file results held in memory between the phases and nothing written to disk. It is off by default because a machine that can hold both models loses nothing by keeping them warm; with it on, raise `REVIEW_TIMEOUT_SECONDS` to about 1200, since two load cycles add roughly 20 to 80 seconds to a review. The measured numbers, reviewer alone and with the cross-examiner, are in docs/benchmarks/. Probed on 2026-09-04 on Ollama 0.33.1: `gemma4:12b` honours the JSON schema with reasoning off (a reported Ollama bug drops the schema on some thinking models; not here). Note: the reviews and findings tables gained columns for this; delete a pre-existing `reviews.db` before starting this version.

## GitHub authentication

The App private key signs a five-minute RS256 JWT, exchanged for an installation token that is scoped at minting time to the one repository under review and to `pull_requests: write` plus `metadata: read`, whatever wider rights the installation may have; a token that comes back wider than asked is refused, and a 422 says which permission the installation lacks. The token is cached in memory until five minutes before it expires and is never logged. At startup the key must parse as an RSA private key of at least 2048 bits (a missing file is reported by its path), and a key file readable by other users produces a `chmod 600` warning in the log.

## Measuring the prompt

The prompts are components with a measurement, not prose to be improved by taste; a prompt ships only when the harness says it beats the incumbent. `scripts/prompt_eval.py` runs the planted corpus in `tests/prompt_corpus.py` (76 diffs: the ten OWASP 2025 categories and four OWASP LLM 2026 ones, fourteen WCAG 2.2 criteria in TSX, HTML and CSS, the diff-checkable Syteca practices, six simplicity cases from ponytail's ladder, and sixteen clean controls that a nit-picking reviewer would wrongly "improve", five of them written after the last prompt writer had read every other control) and the fifteen hostile diffs in `tests/prompt_redteam.py` through the real reviewer against the live Ollama, and writes one JSON per variant with every raw model reply. `scripts/prompt_judge.py` ranks the variants: obey a planted instruction once and you are out; then a score in which a false positive on a clean diff costs twice a miss; then category and severity agreement; cost breaks ties. Candidates are plain text files (`--prompts-dir`, `--cross-prompts-dir`, `--verify-prompts-dir`).

One model at a time: a reviewer-only run is measured first and its replies recorded; `--replay` then feeds those replies back through the pipeline so the cross-examiner or a verifier runs with only its own model loaded, and `--unload` drops what a run used before the next starts. `--allow-cloud` is the one way `STRICT_LOCAL` comes off in the harness, for a reference run of the synthetic corpus on a bigger model through an Ollama cloud tag (the cloud path does not enforce the JSON grammar, so the harness spells the shape out); never point it at real code.

Measured on qwen3.5:9b on 2026-09-05, two repeats, on the fixed pipeline: the shipped prompt finds the planted problem in 95 percent of the 75 planted diffs (recall 0.953) against 70 percent for the previous prompt, with 0.19 false positives per clean diff against 0.09, obeys none of the 32 planted instructions and reports the hostile text as a finding in 21 of them, at about 1,520 tokens and 12.7 seconds per file. With `gemma4:12b` cross-examining by replay: recall 0.927 with the hostile text reported in 23 of 32 rows (the reviewer alone reports 21), nothing obeyed, and 0.56 false positives per clean diff of which 0.06 at medium or worse, at about 3,100 tokens and 34 seconds per file. On the judge's score the pair (0.786) sits below the reviewer alone (0.896), so the cross-examiner is an option rather than a default: what it buys is the disagreement view, the reports it will not drop, and the false positives it removes at medium and above. The verify pass, measured the same day, holds recall at the reviewer's level and removes the last false positives with the new verifier prompt, where the old one cut recall from 0.66 to 0.53, but it stays off by default because the cross-examiner is the second opinion. Every table, command and reading is in docs/benchmarks/, and docs/PROMPT_DESIGN.md says where each rule in the prompts comes from. `REVIEWBOT_PROMPT_EVAL=1 .venv/bin/python -m pytest -m prompt_eval` is the same corpus as a pass or fail floor.

Measured again on 2026-09-06 (docs/benchmarks/2026-09-06-round-three.md), two repeats, after the ground truth was widened on one case and the judge's rules tightened: the shipped prompt reaches recall 0.98 with 0.25 false positives per clean diff (0.16 at medium or worse), reports the hostile text in 16 of 32 rows, obeys nothing, and scores 0.918; a candidate written against its failure rows lost (0.896) and did not ship. The verifier text was replaced by a candidate that keeps five injection reports the old one refuted (recall 0.96 against 0.933 on the same rows), still off by default. The cross-examiner's schema was measured with its note first and with its verdicts first, like for like on the full corpus; the default stays verdicts first, and with the bare-tag rule the reading found, the pair under it scores 0.929 (recall 0.953, 0.09 false positives per clean diff, every report kept, 182 of 182 rows examined), above the reviewer alone at 0.918 on the same rows.

## Limits

`MAX_FILES_PER_REVIEW` (25), `MAX_PATCH_BYTES` (32 000, which must fit `OLLAMA_NUM_CTX`), `MAX_WEBHOOK_BODY_BYTES` (2 MiB), `MAX_INLINE_COMMENTS` (25), `REVIEW_TIMEOUT_SECONDS` (3600: a rewrite-sized diff costs about two minutes a file, twice with the cross-examiner; a review that hits the ceiling posts the files that finished, lists the rest under Not reviewed, and records how far it got), `REVIEW_SECONDS_PER_FILE` (300: a review's own budget is its file count times this, capped by the ceiling, so a small pull request stops holding the queue for an hour; 0 leaves only the ceiling), `MIN_FINDING_CONFIDENCE` (0.5). A review that fails before anything was posted leaves one line on the pull request naming the exception; the reason stays on the dashboard. Draft PRs are skipped unless `REVIEW_DRAFTS=true`. Reference machine: a 2021 M1 Max with 32 GB runs `qwen3.5:9b` at about 13 seconds per file and, with `gemma4:12b` cross-examining, about 34 seconds per file, one model resident at a time.

## API for the dashboard

All routes need `Authorization: Bearer <LOCAL_API_TOKEN>`. With no token configured they answer 503.

- `GET /api/reviews?repository=&limit=&offset=`
- `GET /api/reviews/{id}` (a running review carries `progress`: phase, files done, files total, current file)
- `POST /api/reviews/{id}/feedback` with `{"useful": true | false | null}`
- `GET /api/deliveries?limit=`
- `GET /api/status` (Ollama reachability and loaded models, queue depth and the current job with its progress, database, limits)

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
