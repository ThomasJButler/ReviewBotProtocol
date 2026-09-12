# ReviewBot Protocol

A GitHub App that reviews pull requests with a language model running on your own machine, and a small local dashboard to see what it said. Nothing about the code you review is sent to a model provider. In local mode, the default, the only network peer during a review is api.github.com. A test fails if anything in the backend process opens a connection or resolves a name outside loopback while a review runs, and a container proof runs a review with no network at all.

Built by Tom Butler as a demonstration of private, local AI: AI you own rather than AI you rent. It started as a Codecademy bootcamp project on OpenAI and was rebuilt in September 2026 to run entirely on Ollama, after a security review of the original (see docs/SECURITY_REVIEW.md, which is unsparing).

## What it does

1. You install the App on selected repositories. When a pull request is opened, pushed to, reopened or marked ready for review, GitHub sends a webhook to the backend.
2. The backend verifies the signature, ignores replays, and queues one review per PR head. A single worker fetches the changed files with an installation token.
3. Secret-bearing files are skipped outright. Every other patch is redacted (API keys, tokens, private keys, passwords, encryption and signing keys) before a model sees it.
4. One structured call per file to a local Ollama model, prompted as a specialist security reviewer rather than a general assistant. The diff sits inside a delimited data block the model is told is untrusted, and an instruction planted in the diff is treated as a finding to report, not an order to follow. The answer must fit a fixed JSON schema and findings that quote lines not in the diff are dropped. Optionally a second model from a different family cross-examines each file's review, refuting false positives and adding what the first model missed, with every finding recording which model raised it and where the two disagreed.
5. One review is posted to the PR (a comment review, never an approval), sanitised so the model cannot inject HTML, off-site links or mentions, with a footer naming the model.
6. The dashboard shows what was reviewed, what was said, which file a running review is on, and lets you mark each review useful or not.

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

Four checks, all in the repository:

- `backend/tests/test_runner.py` runs whole reviews through the real code with a fake GitHub API answered in-process and a fake model, under a socket-level guard that fails the test if anything in the process connects or resolves a name outside loopback. It runs in CI.
- `REVIEWBOT_E2E=1 pytest -m e2e` reviews one diff with the real Ollama and model on your machine under the same guard (no GitHub involved). It is skipped by default and never runs in CI.
- `scripts/prove-local.sh` builds a container with the backend, Ollama and a small model, then runs one review with `docker run --network none`. The entrypoint first proves the container has only a loopback interface and no route out. The result is printed, not recorded anywhere; it was last run by hand on 2026-09-03 and passed.
- `backend/scripts/review_diff.py` reviews a branch with no GitHub App and no Docker: it takes a git range, a diff file or stdin, runs the same pipeline the App runs and prints the findings, and it pins `STRICT_LOCAL` on so a cloud model tag is refused however it is configured. Run on 2026-09-12 with the network up, `lsof` sampled the process 84 times over a two-file review and showed `127.0.0.1:11434` as its only peer; the repeat with the wifi off is in docs/TEST_PLAN.md section 6 and is still to do.

## What it is for

A review from this bot is meant to be a stopping point, not another thing to scroll past. AI-assisted development moves faster than understanding, and the hardest part is staying on top of what your own project now contains. So the review is short enough to read whole, each file's summary says what the change does before what is wrong with it, every finding says why the line is a problem, what a senior engineer would write instead and which rule it comes from, and where the two models disagree the review shows both positions rather than picking one for you. Lazy about the solution, never about reading (a line borrowed from ponytail).

Three habits make it a teacher rather than a crutch: read the diff and predict the findings before you open the review; when the reviewer and the cross-examiner disagree, decide who is right before asking either of them why; and when a finding shows the senior version of a line, type the change yourself rather than pasting it.

The prompts were engineered with Claude Fable 5.1 for use with non-frontier local models: a frontier model spent a night and a day writing planted diffs, drafting candidate prompts, reading the small models' raw replies and fixing what it found, and what ships is about 700 words of plain text and a JSON schema that a 9B model runs on a laptop. Every number that claim rests on is in docs/benchmarks/, with the command that produced it, and docs/PROMPT_DESIGN.md says where each rule in the prompts comes from.

What is unusual here, as of a survey on 2026-09-04 (a snapshot; this market changes monthly): self-hosted review on a local model is common, and so are secret redaction, a verification pass and a chat with the reviewer. Nothing found combines a runnable proof that nothing leaves the machine, two model families cross-examining each other with the disagreement shown and every finding's provenance recorded, a prompt that ships only when a planted-diff harness says it beats the incumbent, and learning as the goal. Each of those is checkable in this repository; none of them is a promise.

## See it in action

The hands-on test plan was run against a public scratch repository on 2026-09-06 and the pull requests are left open as examples of what the bot posts:

- [PR 1, the planted pull request](https://github.com/ThomasJButler/ReviewBot-Protocol-Testing/pull/1): an SQL injection, two made-up keys, an instruction planted in a comment, a command injection, a `.env` file, a minified bundle and a rename. Four reviews, one per push; the last cross-examined by `gemma4:12b`.
- [PR 2, opened as a draft](https://github.com/ThomasJButler/ReviewBot-Protocol-Testing/pull/2): skipped until it was marked ready, then reviewed with no findings.
- [PR 3, thirty files](https://github.com/ThomasJButler/ReviewBot-Protocol-Testing/pull/3): twenty-five reviewed, five listed as over the cap.
- [PR 4](https://github.com/ThomasJButler/ReviewBot-Protocol-Testing/pull/4), [PR 5](https://github.com/ThomasJButler/ReviewBot-Protocol-Testing/pull/5) and [PR 6](https://github.com/ThomasJButler/ReviewBot-Protocol-Testing/pull/6): a small Mandelbrot renderer built the way a junior would, across three stacked pull requests, reviewed by the 9B with `gemma4:12b` cross-examining. Unbounded query parameters, a save path joined from user input, debug mode on the network, a gallery page with no `lang`, colour-only status and a `div` as a button, titles inserted with `innerHTML`, a file route with no containment check, a pickle cache and a hard-coded placeholder secret: read the reviews and decide which findings you agree with.

What each scenario expected and what happened is in docs/TEST_PLAN.md, section 8.

## Quick start

You need Python 3.13, Node 22 with npm 11, Ollama, and a GitHub App you own. This is the short form; the same setup at length, with GitHub's documentation linked at every step, is docs/TEST_PLAN.md sections 1 to 4.

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

Dashboard, from the repository root:

```
npm install                   # npm 11 or newer
cp .env.example .env.local   # BACKEND_URL and the same LOCAL_API_TOKEN
npm run dev                   # http://127.0.0.1:3000
```

The App: webhook URL your public URL ending in `/webhook/github`, webhook secret the output of `openssl rand -hex 32` and the same value in `backend/.env`, SSL verification left enabled, permissions Pull requests read and write plus Metadata read and nothing else, subscribed to the Pull request event only, installed on selected repositories rather than all of them. Generate the App's private key, move the downloaded `.pem` outside the repository, `chmod 600` it, and point `GITHUB_PRIVATE_KEY` at that path.

Expose only `POST /webhook/github` on the backend to the internet (a tunnel or a reverse proxy) and add that hostname to `ALLOWED_HOSTS` as a bare name in the comma-separated list: `ALLOWED_HOSTS=localhost,127.0.0.1,<tunnel-host>`. A tunnel that forwards the whole port also exposes `/health` and the dashboard API, which is then protected by `LOCAL_API_TOKEN` alone, so make that token long and prefer a proxy rule that forwards only the webhook path.

For a hands-on run, one command brings the three processes up with the tunnel: `NGROK_DOMAIN=<your static ngrok domain> scripts/dev-up.sh` starts ngrok, the dashboard and the backend, and Ctrl-C stops all three. It starts the backend with `uvicorn main:app`, which is the same server `python main.py` runs.

The check that it all came up: open http://127.0.0.1:3000/status, which should show Ollama reachable, the model present and the review worker Running.

The dashboard has no login. It binds to 127.0.0.1 only, refuses any other Host name, and must stay that way: anyone who can open it can read every review, including quoted lines of private code. If you ever want it reachable from elsewhere, put a real credential in front of it.

Every setting, with its default and what raising it costs, is in docs/SETTINGS.md (generated from the settings class); the App in more detail is in backend/README.md and on the dashboard's Setup page.

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
