# Settings reference

Generated from `backend/config/settings.py` by `backend/scripts/settings_reference.py`; regenerate rather than edit (`cd backend && .venv/bin/python scripts/settings_reference.py > ../docs/SETTINGS.md`). Every setting is read from the environment or from `backend/.env`; `backend/.env.example` is the starting point. Types are what the setting is parsed to; a boolean accepts true, 1, yes or on.

<!-- prettier-ignore -->
| Setting | Type | Default | What it does, what it costs |
| --- | --- | --- | --- |
| `APP_NAME` | str | `ReviewBot Protocol` | The name in the startup log and the API's OpenAPI title. Cosmetic. |
| `APP_VERSION` | str | `1.1.0` | The version /health and /api/status report, matching the CHANGELOG entry. Bumped with a release. |
| `DEBUG` | bool | `false` | Console-formatted logs instead of JSON lines, and FastAPI's debug mode. Off for anything GitHub can reach. |
| `HOST` | str | `127.0.0.1` | The interface uvicorn binds. Loopback by default: GitHub reaches the webhook through a tunnel or a reverse proxy that forwards only that path, never through this port being public. |
| `PORT` | int | `8000` | The port uvicorn binds. The dashboard's BACKEND_URL and scripts/dev-up.sh point at it. |
| `ALLOWED_HOSTS` | str | `localhost,127.0.0.1` | Comma-separated bare hostnames the backend answers for (the Host header check). Add the tunnel or proxy hostname without scheme or path; a pasted URL is reduced to its hostname. Loopback only means GitHub cannot reach the webhook, and startup says so. |
| `ALLOWED_ORIGINS` | str | `http://localhost:3000` | Comma-separated origins allowed by CORS. The dashboard calls the backend server-side, so this rarely changes. |
| `GITHUB_APP_ID` | str | required | The App's numeric id from its settings page. Required. |
| `GITHUB_PRIVATE_KEY` | str | required | The App's private key: PEM text, a path to the .pem file (outside the repository at mode 600, or startup warns), or base64 of the PEM. Required; a key that cannot sign a JWT fails at startup, not at the first webhook. |
| `GITHUB_WEBHOOK_SECRET` | str | required | The secret typed into the App's webhook form; every delivery's signature is checked against it before the body is parsed. Required, at least 16 characters: openssl rand -hex 32. |
| `GITHUB_API_BASE_URL` | str | `https://api.github.com` | GitHub's REST API, the one host the backend talks to besides Ollama. Changes only for GitHub Enterprise Server. |
| `OLLAMA_BASE_URL` | str | `http://127.0.0.1:11434` | Where Ollama listens. Under STRICT_LOCAL it must be a loopback address, which is the whole privacy claim. |
| `OLLAMA_MODEL` | str | `qwen3.5:9b` | The reviewer model's Ollama tag, the one the prompts were measured against (docs/benchmarks). A bigger model costs more seconds per file and more memory; measure before switching. |
| `OLLAMA_NUM_CTX` | int | `16384` | The context window in tokens. MAX_PATCH_BYTES must fit inside it beside the prompt and the reply; raising it lets a bigger file through and costs memory per resident model, roughly in proportion. |
| `OLLAMA_NUM_PREDICT` | int | `2000` | The most tokens one reply may have. The schema caps findings at twenty, so a reply rarely nears it; lower and a long review is cut mid-JSON and lost. |
| `OLLAMA_TEMPERATURE` | float | `0.1` | Sampling temperature, the value the prompts were measured at. Higher gives more varied findings and more false positives. |
| `OLLAMA_KEEP_ALIVE` | str | `30m` | How long Ollama keeps the reviewer loaded after a call. Shorter frees memory sooner and reloads the model for the next review, about ten seconds on the reference laptop. |
| `OLLAMA_TIMEOUT_SECONDS` | int | `600` | The HTTP timeout for one model call, in seconds. A rewrite-sized file on the 9B takes about two minutes; a call that hits this is a failed file, not a failed review. |
| `REVIEW_TIMEOUT_SECONDS` | int | `3600` | The ceiling on one review, in seconds. A review that hits it posts the files that finished, lists the rest under Not reviewed and records how far it got. A rewrite-sized diff costs the 9B about two minutes a file, twice with the cross-examiner, so 25 files can need most of an hour. |
| `REVIEW_SECONDS_PER_FILE` | int | `300` | The review's own budget: its file count times this, never above the ceiling, minus a 60 second margin so it fires first. A two-file pull request then stops holding the queue for an hour. 0 leaves only the ceiling. |
| `REVIEW_DRAFTS` | bool | `false` | Review draft pull requests too. Off: a draft is recorded as skipped_draft and reviewed when marked ready. |
| `REVIEW_BOT_PULL_REQUESTS` | bool | `false` | Review pull requests opened by a bot (dependabot, renovate). Off: they are recorded as skipped_bot; each would cost the machine about an hour. |
| `REVIEW_RETENTION_DAYS` | int | `365` | Reviews, their findings and webhook deliveries older than this many days are deleted at startup and then nightly, never a row still running. 0 keeps everything. A deleted review's dashboard link becomes a 404, so scripts/export_reviews.py writes what is worth keeping to JSON first. |
| `MAX_FILES_PER_REVIEW` | int | `25` | The most files one review reads, riskiest first by path and size; the rest are listed under Not reviewed. Each file is one model call, two with the cross-examiner. |
| `MAX_PATCH_BYTES` | int | `32000` | The largest per-file diff sent to the model, in bytes. At about 2.8 bytes a token it must fit OLLAMA_NUM_CTX beside the prompt and the reply; a bigger file is skipped with a reason, never truncated. |
| `MAX_WEBHOOK_BODY_BYTES` | int | `2097152` | The most bytes a webhook delivery may carry, checked on Content-Length and again while streaming, before the signature check. GitHub's pull request payloads are far smaller. |
| `MAX_INLINE_COMMENTS` | int | `25` | The most findings attached as inline review comments; the rest go into the review body, since GitHub rejects a review with too many. |
| `MIN_FINDING_CONFIDENCE` | float | `0.5` | A finding the model rates below this confidence is dropped. The measured false-positive rate assumes this value; lower keeps more of the model's doubts. |
| `VERIFY_FINDINGS` | bool | `false` | A second pass by the same model that tries to refute each finding before it is posted. Off: measured in docs/benchmarks, it removes some false positives at one extra call per finding. |
| `MAX_VERIFY_CALLS_PER_REVIEW` | int | `40` | The verify pass stops after this many calls in one review; later findings are posted unverified. |
| `CROSS_EXAMINE_MODEL` | str | empty | The Ollama tag of a second model from a different family that judges every finding and may add its own (gemma4:12b was measured). Empty means off. One call per file, and with both models resident their memory together. |
| `CROSS_EXAMINE_MAX_CALLS_PER_REVIEW` | int | `25` | The cross-examiner stops after this many calls in one review, one per file; later files keep the first review. |
| `CROSS_EXAMINE_KEEP_ALIVE` | str | `30m` | How long Ollama keeps the cross-examiner loaded after a call, like OLLAMA_KEEP_ALIVE. |
| `CROSS_EXAMINE_SEQUENTIAL` | bool | `false` | Run the two models one at a time: review every file, unload the reviewer, cross-examine every file, unload the cross-examiner. For a machine that cannot hold both at once (the 32 GB reference laptop); costs a reload between the phases. |
| `CROSS_EXAMINE_NOTE_FIRST` | bool | `false` | The cross-examiner writes its summary note before its verdicts. Measured both ways in docs/benchmarks; verdicts first (off) scored higher on the corpus. |
| `LOCAL_API_TOKEN` | str | empty | The bearer token the dashboard sends on every /api call; the same value goes in the dashboard's .env.local. Empty leaves the dashboard routes open, safe only while the port is loopback. |
| `STRICT_LOCAL` | bool | `true` | The local-only guard: refuse to start if OLLAMA_BASE_URL is not loopback, a model tag looks like an Ollama cloud model, or a cloud API key (OpenAI, Anthropic, Google, Mistral, Sentry, LangSmith) is in the environment. LangSmith tracing variables are fatal regardless. False only when your shell carries keys for other projects. |
| `LOG_LEVEL` | str | `INFO` | The logging level for the backend's JSON log lines. |
| `LOG_PROMPTS` | bool | `false` | Log the full prompt of every model call, diff included. Off; on only for a debugging session, since the log then holds the code. |
| `DATABASE_URL` | str | `sqlite:///./reviews.db` | Where reviews live, relative to the backend directory. One backend per database, enforced by a lock file beside it. |
| `DATABASE_ECHO` | bool | `false` | Log every SQL statement the backend runs. Off; on only while debugging the database layer. |
