# Changelog

Each release lists what changed for someone running it. The numbers quoted anywhere in the repository point at the tagged commit; `docs/benchmarks/` holds the measurements with the commands that regenerate them.

## Unreleased

- A review cut short by the time ceiling posts the files that finished and lists the rest under Not reviewed; each review also gets its own budget of `REVIEW_SECONDS_PER_FILE` (300) times its file count, under the ceiling; a review that fails before posting leaves one line on the pull request.
- A forged data-block delimiter inside a diff is rewritten to `[forged-data-marker]`. It was `[data-marker]`, which the verifier read as the pipeline's own framing before standing down on a planted instruction (`docs/benchmarks/2026-09-06-round-three.md`). Naming the token in the prompts is a separate change and waits on a measured round.
- A simplicity finding titled with the tag list rather than the problem is dropped, and one titled with the prompt's own sentence is retitled from its recommendation rather than dropped, because the finding under that title is often right.
- A finding whose recommendation praises the line and asks for nothing is dropped, from either model, and every finding the postprocess drops is logged with its rule; measured by replay, the reviewer alone goes from 0.918 to 0.929 on the corpus, one clean-diff false positive fewer, with recall unchanged.
- Pull requests opened by a bot (dependabot, renovate) are skipped unless `REVIEW_BOT_PULL_REQUESTS=true`; a skipped delivery is recorded as `skipped_bot`, and the Status page shows this setting beside the draft one.
- The replay check's body hash is a unique index, so the read-then-insert race is a constraint; an existing database gets the index at startup, or a warning if it holds duplicates.
- `REVIEW_RETENTION_DAYS` (365): reviews, their findings and webhook deliveries older than that are deleted at startup and nightly, never a row still running; 0 keeps everything. `scripts/export_reviews.py` writes what is worth keeping to JSON first.
- Every setting carries a docstring, and `docs/SETTINGS.md` is generated from them by `scripts/settings_reference.py`; a test keeps the file and the class equal.
- The dashboard's section cards on the Status and Setup pages are headings, so the page outline reads the way it looks; a root error page (`app/global-error.tsx`) paints a fallback when the layout itself fails.
- The setup steps say the same thing in the README, the backend README and the test plan; the troubleshooting table carries the rows the live runs turned up; the hosted-model plan and the security review say what they are and what superseded them; `docs/benchmarks/HOW_TO_RUN_A_ROUND.md` writes down how a measurement round is run.

## 1.1.0 (2026-09-07)

The local rewrite. Reviews run on models on your own machine through Ollama; nothing leaves it but api.github.com, and a test proves it.

- A second model from a different family cross-examines every finding, and the disagreements are shown rather than hidden.
- Prompts ship only when a planted-diff harness says so. The numbers are in `docs/benchmarks/` with the commands that regenerate them.
- A dashboard with four screens: the reviews, one review with its findings and the posted comment, status, and setup.
- Six reviewed pull requests on the public scratch repository (`ThomasJButler/ReviewBot-Protocol-Testing`) show what it posts.
- Runs on a 2021 M1 Max with 32 GB, one model resident at a time; the limits and their costs are in `backend/README.md`.
