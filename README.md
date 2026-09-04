# ReviewBot Protocol

A GitHub App that reviews pull requests with a language model running on your own machine, and a small local dashboard to see what it said. Nothing about the code you review is sent to a model provider. In local mode, the default, the only network peer during a review is api.github.com. A test fails if anything in the backend process opens a connection or resolves a name outside loopback while a review runs, and a container proof runs a review with no network at all.

Built by Tom Butler as a demonstration of private, local AI: AI you own rather than AI you rent. It started as a Codecademy bootcamp project on OpenAI and was rebuilt in September 2026 to run entirely on Ollama, after a security review of the original (see docs/SECURITY_REVIEW.md, which is unsparing).

## What it does

1. You install the App on selected repositories. When a pull request is opened, pushed to, reopened or marked ready for review, GitHub sends a webhook to the backend.
2. The backend verifies the signature, ignores replays, and queues one review per PR head. A single worker fetches the changed files with an installation token.
3. Secret-bearing files are skipped outright. Every other patch is redacted (API keys, tokens, private keys, passwords) before a model sees it.
4. One structured call per file to a local Ollama model, prompted as a specialist security reviewer rather than a general assistant. The diff sits inside a delimited data block the model is told is untrusted, and an instruction planted in the diff is treated as a finding to report, not an order to follow. The answer must fit a fixed JSON schema; findings that quote lines not in the diff are dropped; an optional second pass asks the model to disprove each finding before it is posted.
5. One review is posted to the PR (a comment review, never an approval), sanitised so the model cannot inject HTML, off-site links or mentions, with a footer naming the model.
6. The dashboard shows what was reviewed, what was said, and lets you mark each review useful or not.

## What it deliberately does not do

- It never approves, requests changes, or sets commit statuses. Nothing the model says can gate a merge.
- It has no cloud fallback. If Ollama is down, reviews fail visibly and are recorded as failed.
- It has no manual paste-your-code mode, no GitHub OAuth, no multi-user anything. It is a tool for one person's repositories.
- It is not a product. It is well tested for what it does, and it has been run end to end on real pull requests by exactly one person.

## Privacy, stated precisely

Leaves the machine: HTTPS requests to api.github.com to read the PR, its files, and post the review. That is the complete list.

Never leaves the machine in local mode: the diff, the prompt, the model's output. The backend refuses to start if the environment contains a LangSmith tracing flag or an OpenAI, Anthropic, Google, Mistral or Sentry key (`STRICT_LOCAL`, on by default). No telemetry, no analytics, no fonts or scripts from a CDN in the dashboard. Next.js telemetry is disabled in the scripts.

Stored on your disk (SQLite): repository, PR number and title, head SHA, model, timings, token counts, the skipped files, the posted review body, and each finding, including the quoted line of the redacted diff it is about. Whole patches are not stored. Logs never contain diffs or model output unless you set `LOG_PROMPTS=true`.

Hosted mode, optional: the same bot, unchanged, on a server you rent so a stronger open model (qwen3-coder:30b) is not blocked by your laptop. Ollama stays on loopback there and only the webhook is exposed, but the diff is then processed on hardware you rent rather than own, and the README's local claims describe local mode only. Costs, providers and the step-by-step are in docs/HOSTED_MODEL_PLAN.md.

Ollama: bound to loopback. The desktop app checks ollama.com hourly for updates of itself (never prompt content); run `ollama serve` from a terminal instead if you want no outbound connection at all. `OLLAMA_NO_CLOUD=1` disables Ollama's cloud features (remote inference and web search). A cloud-hosted model tag such as `gpt-oss:120b-cloud` would make a local Ollama relay every prompt off the machine; the backend refuses such a tag under `STRICT_LOCAL`, but set `OLLAMA_NO_CLOUD=1` as well.

### The proof

Three checks, all in the repository:

- `backend/tests/test_runner.py` runs whole reviews through the real code with a fake GitHub API answered in-process and a fake model, under a socket-level guard that fails the test if anything in the process connects or resolves a name outside loopback. It runs in CI.
- `REVIEWBOT_E2E=1 pytest -m e2e` reviews one diff with the real Ollama and model on your machine under the same guard (no GitHub involved). It is skipped by default and never runs in CI.
- `scripts/prove-local.sh` builds a container with the backend, Ollama and a small model, then runs one review with `docker run --network none`. The entrypoint first proves the container has only a loopback interface and no route out. The result is printed, not recorded anywhere; it was last run by hand on 2026-09-03 and passed.

## Quick start

You need Python 3.13, Node 22, Ollama, and a GitHub App you own.

Backend:

```
cd backend
python3.13 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements.lock
.venv/bin/pip install -r requirements-dev.txt   # requirements.txt is only the input to pip-compile
cp .env.example .env      # GitHub App id, private key path, webhook secret, and a LOCAL_API_TOKEN
ollama pull qwen3.5:9b
.venv/bin/python main.py  # 127.0.0.1:8000
```

Dashboard:

```
npm install                   # npm 11 or newer
cp .env.example .env.local   # BACKEND_URL and the same LOCAL_API_TOKEN
npm run dev                   # http://127.0.0.1:3000
```

The dashboard has no login. It binds to 127.0.0.1 only, refuses any other Host name, and must stay that way: anyone who can open it can read every review, including quoted lines of private code. If you ever want it reachable from elsewhere, put a real credential in front of it.

Expose only `POST /webhook/github` on the backend to the internet (a tunnel or a reverse proxy), add that hostname to `ALLOWED_HOSTS`, and point the App's webhook at it. A tunnel that forwards the whole port also exposes `/health` and the dashboard API, which is then protected by `LOCAL_API_TOKEN` alone, so make that token long and prefer a proxy rule that forwards only the webhook path. The full App setup, permissions (Pull requests read and write, Metadata read, nothing else) and all settings are in backend/README.md and on the dashboard's Setup page.

## Choosing a model

The honest trade-off: a local model is not GPT-4o, and a small one is a triage layer, not an unattended reviewer.

| Model             | Disk   | On an M1 Max 32 GB                                                                  | What to expect                                                                                           |
| ----------------- | ------ | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `qwen3.5:9b`      | 6.6 GB | about 33 tokens per second, fully on GPU (one observation on an M1 Max, 2026-09-03) | catches obvious injection, hard-coded secrets and clear bugs; misses subtle logic; can over-report style |
| `qwen3-coder:30b` | 19 GB  | mixture-of-experts, 45 to 60 tokens per second estimated                            | the recommended primary when you have the disk; needs `OLLAMA_NUM_CTX=16384` on 32 GB                    |
| `qwen3.6:27b`     | 17 GB  | dense, 12 to 16 tokens per second estimated                                         | strongest on benchmarks; slow enough that a 20-file PR takes a while                                     |

Vendor benchmark numbers and the reasoning behind these picks are in docs/LOCAL_MIGRATION.md. Findings are checked against the diff before posting, which removes most of what a small model invents; it does not make a small model clever.

## Repository layout

```
backend/     FastAPI service: webhook, queue, redaction, review pipeline, dashboard API, tests
app/ components/ lib/   Next.js dashboard (four screens: reviews, review detail, status, setup)
docs/        SECURITY_REVIEW.md (three review rounds, every finding and its status), LOCAL_MIGRATION.md (design), FRONTEND_PLAN.md
scripts/     prove-local.sh and the container proof
.github/     CI (tests, lint, types, build, audits) and Dependabot
```

## Licence

MIT.
