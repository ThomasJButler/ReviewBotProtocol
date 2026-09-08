# Changelog

Each release lists what changed for someone running it. The numbers quoted anywhere in the repository point at the tagged commit; `docs/benchmarks/` holds the measurements with the commands that regenerate them.

## Unreleased

## 1.1.0 (2026-09-07)

The local rewrite. Reviews run on models on your own machine through Ollama; nothing leaves it but api.github.com, and a test proves it.

- A second model from a different family cross-examines every finding, and the disagreements are shown rather than hidden.
- Prompts ship only when a planted-diff harness says so. The numbers are in `docs/benchmarks/` with the commands that regenerate them.
- A dashboard with four screens: the reviews, one review with its findings and the posted comment, status, and setup.
- Six reviewed pull requests on the public scratch repository (`ThomasJButler/ReviewBot-Protocol-Testing`) show what it posts.
- Runs on a 2021 M1 Max with 32 GB, one model resident at a time; the limits and their costs are in `backend/README.md`.
