# Changelog

Each release lists what changed for someone running it. The numbers quoted anywhere in the repository point at the tagged commit; `docs/benchmarks/` holds the measurements with the commands that regenerate them.

## Unreleased

- A review cut short by the time ceiling posts the files that finished and lists the rest under Not reviewed; each review also gets its own budget of `REVIEW_SECONDS_PER_FILE` (300) times its file count, under the ceiling; a review that fails before posting leaves one line on the pull request.
- A forged data-block delimiter inside a diff is rewritten to `[forged-data-marker]`. It was `[data-marker]`, which the verifier read as the pipeline's own framing before standing down on a planted instruction (`docs/benchmarks/2026-09-06-round-three.md`). Naming the token in the prompts is a separate change and waits on a measured round.

## 1.1.0 (2026-09-07)

The local rewrite. Reviews run on models on your own machine through Ollama; nothing leaves it but api.github.com, and a test proves it.

- A second model from a different family cross-examines every finding, and the disagreements are shown rather than hidden.
- Prompts ship only when a planted-diff harness says so. The numbers are in `docs/benchmarks/` with the commands that regenerate them.
- A dashboard with four screens: the reviews, one review with its findings and the posted comment, status, and setup.
- Six reviewed pull requests on the public scratch repository (`ThomasJButler/ReviewBot-Protocol-Testing`) show what it posts.
- Runs on a 2021 M1 Max with 32 GB, one model resident at a time; the limits and their costs are in `backend/README.md`.
