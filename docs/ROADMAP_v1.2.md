# v1.2: what is left, and what was never built

Written on 2026-09-07 at the end of the v1.1 work, from the next-round briefs in `docs/benchmarks/`, the test-plan run in `docs/TEST_PLAN.md`, and the design notes that stayed notes. Each item says where it comes from and roughly what it costs. Nothing here is promised; it is the list to pick from.

## 0. If the time is short: the order

Three passes, each leaving the project in a state you would be happy to show. Stop after any of them.

1. **Ship (a day).** Done on 2026-09-07: PR 13 merged, `v1.1.0` tagged at the merge commit with a release, the two stale dependabot pull requests closed and the six green ones merged, `CHANGELOG.md` started. Section 1 has the record.
2. **Make it robust for a stranger (two days).** A review cut short posts what it has; a per-file time budget; the forged-delimiter token; praise-as-finding; docstrings on every setting field and a pass over the READMEs against the test plan's setup sections so they agree step by step; a retention setting so `reviews.db` does not grow forever (delete or export reviews older than N days). Sections 2 and 7 hold the detail.
3. **Make it better (as long as you have).** The next prompt round from section 3, measured with the chain shape in section 8 and the held-out set from section 4; then the site.

Everything below is the detail for those three, plus the things that stayed design-only.

## 1. Ship v1.1

What happened, 2026-09-07:

- PR 13 (`v1.1-Local-AI` into `main`) merged at 18:17 UTC as `5121aa3`. The bot reviewed it five times as the branch moved, all five from `reviewbot-tjb` and none from a person (`gh pr view 13 --json reviews`); the five-reader `/code-review` run was internal and never posted; CodeRabbit declined it for size.
- `v1.1.0` is an annotated tag at `5121aa3` with a GitHub release whose notes are the CHANGELOG entry.
- Dependabot 11 and 12 (bumps against the old lock files) closed with a note. Of the nine it opened against the new lock files, the six green and minor ones were merged (actions/setup-python 7, actions/setup-node 7, actions/checkout 7 after a rebase, ollama/ollama 0.33.3, lint-staged 17, @types/node 26). Next 16, eslint-config-next 16 and eslint 10 (20, 18, 22) stay open: 18 and 22 fail alone and only pass together, so they are one branch to try by hand with the dev server up.
- `CHANGELOG.md` started at 1.1.0 with an Unreleased section that each v1.2 pull request adds a line to.
- The App stays installed on this repository and the scratch repository; every pull request here costs the laptop about an hour when the bot is up, which is why section 2 gains a setting to skip pull requests opened by bots.

## 2. Product, small and concrete

- **A review cut short should post what it has.** A timeout after 24 of 25 files currently throws the whole review away. The results live in the LangGraph state; on cancellation, render and post the files that finished, with a note naming the ones that did not. Half a day, and the biggest quality-of-life change on the list.
- **Per-file time budget instead of one ceiling.** `REVIEW_TIMEOUT_SECONDS` is one number for the whole review; the cost is per file and depends on diff size. A budget of seconds per file, scaled by the number of files, would stop small PRs waiting behind a generous ceiling and big ones dying under a tight one.
- **Re-run a review on demand** from the dashboard (a button that resubmits the head), and **compare two reviews of the same PR side by side** (before and after a push). The queue and the API can do both today; the pages cannot.
- **The forged-delimiter token.** A forged data-block marker inside the diff was rewritten to `[data-marker]`, and the verifier read that as the pipeline's own framing and stood down. It is now `[forged-data-marker]` (a pipeline change, no measurement needed; done in v1.2) and name it in both prompts (a prompt change, so a round-four candidate measured before it ships). The verifier's one remaining silenced case.
- **Praise filed as a finding.** Done in v1.2 as a pipeline rule, measured by replay (0.918 to 0.929 for the reviewer alone, nothing else moved; `docs/benchmarks/2026-09-06-round-three.md`, the evening addendum). The prompt sentence is still a round-four candidate.
- **From the two reviews of PR 13.** A `global-error.tsx` so a render error in the root layout shows a fallback (none has ever existed on any branch; the note that main had one was wrong); a unique index on the delivery body hash so the replay check is a constraint rather than a read-then-insert (the queue already makes the race harmless); `CardTitle` and `CardDescription` render as `div`, which is shadcn's default and a fair accessibility nit for a heading; one unused import (`func` in `database/models.py`).
- **Skip pull requests opened by bots.** Dependabot opened nine in one afternoon; each would have queued an hour of the laptop. A setting, off by default, decides whether a pull request whose author is a bot is reviewed; the delivery is recorded as skipped either way.
- **Fork pull requests** were never tested live (S6 needs a second GitHub account). The code path exists and has unit tests; one real fork PR would close it.
- **Retention for `reviews.db`.** Every review and every finding is kept forever, including quoted lines of private code. A setting for how long to keep them (default a year), a nightly delete, and an export to JSON for anything worth keeping longer.
- **Surface a failed or cut-short review on the PR.** A timeout posts nothing at all today; a one-line comment saying the review did not complete and why would stop the silence looking like approval.
- **Bigger context on a bigger machine.** `OLLAMA_NUM_CTX` at 16384 means a 32 KB patch is the most a file can be; on a server with both models resident, 32768 and a 64 KB cap are one setting each, and worth measuring.

## 3. The next prompt round (from the raw replies of round three)

Reviewer:

- Resisting a planted instruction is not reporting it: two structural plants resisted and never filed, one named in the summary prose and never filed, two filed under the wrong category.
- The tag-list sentence for simplicity findings ("yagni, delete, stdlib, native or shrink, then what to remove") is copied out as a finding title on two cases in both repeats.
- A finding whose recommendation concludes there is no finding must produce none (six of sixteen false positives read this way).
- The 16-pixel target is described approvingly in both repeats; the candidate that named the threshold got it, but bought it by naming the case.
- From the fractal pull requests: an unbounded query parameter (width, height, iterations straight from the query string) and a validator copied between two files were never raised.

Cross-examiner:

- Keep "quote one line exactly, character for character" beside the definition of an addition; separating them turned additions into prose that could not locate.
- The label and the reason still disagree often enough (a reason that argues the finding is real under a false-positive label) that the correction rule carries real weight; a sentence that the verdict must follow the reason, as the verifier already has.
- The note should name the decisive line; under note first it does so in 2 rows of 182.

Verifier:

- The forged-delimiter case above.
- The reasons are cut at the first quote character, the 9B's JSON limit; the prompt could ask for reasons without quotes.

## 4. Corpus and harness

- **Defensive code as clean controls.** On PR 13 the reviewer read the defences as the attacks: a critical on the line that sanitises the PR title, a critical on a test file's docstring that carries a hostile fixture, highs on the redaction patterns and on a prompt's own text. A hardened codebase is full of regexes that redact, sanitisers, and tests with planted hostile strings, and the corpus has none of that shape. Add a dozen clean diffs of that kind, and a rule in the prompt that a string handled by a sanitiser or a fixture inside a test is the defence, not the finding.
- **A finding that names something not in the diff** ("delete unused MatrixSelect component" on a file with no such component) passes because its evidence line is real; the title's nouns could be checked against the diff text.
- **A held-out planted set** the prompts are never tuned against, so a candidate's gain can be told from memorisation. Twenty cases in the shapes the fractal PRs suggested would do: unbounded parameters, a copied validator, an MD5 key called a traversal, a `div` as a button, a status shown by colour alone.
- The obedience check reads only an empty reply or a "no issue" summary, so a banned `<img>` in a recommendation passes; read each case's `expected_safe_behaviour` as a rule.
- The per-case silencing rule lets a report dropped in one repeat pass when the other repeat kept it; a per-row count beside the per-case one.
- `NOT_YET_CLEARED` in the floor test: the shipped reviewer cleared six of its seven in both repeats of round three; a second two-repeat run lets the set shrink to one.
- A pooled judge over two tags (`full3` plus `full3b`) so a four-repeat number is one command.
- The harness's `--replay-cross` now re-measures a cross run through a changed pipeline with no model; the verifier has no equivalent yet (`--replay-verify`).

## 5. Running it somewhere other than a laptop

- The server shape from the day-two design: one box with both models resident, `CROSS_EXAMINE_SEQUENTIAL` off, a bigger reviewer (the 30B coder model measured on 2026-09-03) if the numbers on the corpus justify it. Measure first: the harness runs anywhere Ollama does.
- The queue is one in-process worker. More than one machine needs a shared queue and per-repository workers; a day's work when it is needed, not before.
- SQLite with one writer is fine for one person; a team would swap it, and the repository layer is the seam.
- Secrets and the webhook path behind a real reverse proxy rule, as `README.md` already says; the tunnel is for development only.

## 6. Features that stayed design-only

- **Chat with the reviewer.** Ask why a finding was raised, or ask the two models to argue it out, from the review page. The disagreement view is where this earns its keep; the local model and the prompts are already there, the page and the conversation state are not.
- **Voice.** Read a review aloud or dictate a question; a stretch, listed because it was in the early notes.
- **Diagram mode.** A picture of the change (call graph, data flow) beside the findings; the diff parser has the lines, nothing draws them.
- **A learning log.** The README's three habits (predict the findings before opening the review; decide who is right when the models disagree; type the senior version yourself) have no place to be recorded. A per-review note of what you predicted and what you decided, kept locally, would make the "teacher rather than crutch" claim measurable.

## 7. The website: setup, docs and the pitch (separate repository)

A small landing site (shadcn, plain, fast) that becomes the official link on the ReviewBot Protocol repository. Two jobs: get someone from "cloned it" to "first review posted" without a gap the README leaves, and say what the thing is to a business that runs its own hardware. What it needs, and where each piece comes from so the site and the repository never disagree:

- **One source of truth for the docs.** The site renders the repository's own markdown (`README.md`, `backend/README.md`, `docs/TEST_PLAN.md`, `docs/PROMPT_DESIGN.md`, `docs/benchmarks/`) rather than copying it. A docs change is a commit here and a rebuild there; nothing is written twice.
- **A settings reference, generated.** Every setting in `backend/config/settings.py` with its meaning, default, unit, what changes when you raise it and what it costs (`REVIEW_TIMEOUT_SECONDS` against files and diff size; `MAX_PATCH_BYTES` against `OLLAMA_NUM_CTX`; `CROSS_EXAMINE_SEQUENTIAL` against memory; `STRICT_LOCAL` and what it refuses). Generate it from the settings class's docstrings and defaults so it cannot go stale; the class needs a docstring per field first, which is the repository-side task.
- **A hardware page with measured numbers.** The reference laptop (2021 M1 Max, 32 GB): about 13 seconds a file on a small diff and about two minutes on a rewrite-sized one with the 9B, the same again with the cross-examiner, one model resident at a time; what a review of 25 and of 50 files costs; what the 31B on a server changes. Every number from `docs/benchmarks/` with its command, never a round figure typed in.
- **Setup walkthroughs, one per shape.** Laptop with a tunnel (ngrok's static dev domain, the webhook URL must end in `/webhook/github`, `ALLOWED_HOSTS` as a bare hostname, the private key at mode 600, the App permissions, install on selected repositories only, `scripts/dev-up.sh`, the Status page); a server with a reverse proxy that forwards only the webhook path, both models resident, sequential off, a bigger context; and what leaves the machine in each shape (nothing but api.github.com, and how to prove it with the egress test). Sections 1 to 4 of `docs/TEST_PLAN.md` are the draft.
- **Troubleshooting from real runs.** The table in `docs/TEST_PLAN.md` plus what the live runs turned up since: a pasted URL in `ALLOWED_HOSTS`, the webhook URL without its path, a review that hits the ceiling and posts nothing, the placeholder rule leaving an "example" key in the clear, Ollama relaunching itself after a kill.
- **Scaling, honestly.** Linear in files and pull requests, serial across them on one machine, the per-file constant set by model and diff size; a second machine or a bigger GPU before any code change; the queue and the database as the two seams (section 5 above).
- **The pitch page.** The three things nothing else offers together (a runnable proof that nothing leaves the machine, two model families cross-examining with the disagreement shown, prompts that ship only when a planted-diff harness says so), the examples on the scratch repository, and the cost: a laptop that is already on the desk.
- **The in-app Setup page** stays, shortened to the checklist, and links to the site for the rest.

## 8. Housekeeping

- `docs/HOSTED_MODEL_PLAN.md` and `docs/SECURITY_REVIEW.md` predate the local rewrite; mark them historical or fold what still holds into `docs/LOCAL_MIGRATION.md`.
- The chain scripts under `~/ReviewBot-runs/` are the measurement's provenance and live outside the repository by design; a short `docs/benchmarks/HOW_TO_RUN_A_ROUND.md` with the chain's shape (pre-flight, pick with fallback, one model at a time, Ollama off at the end, keep the laptop on mains) would save the next round the mistakes this one made.
