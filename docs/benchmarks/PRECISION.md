# Precision on real pull requests

Every other file in this directory measures recall: a diff with a planted bug, does the reviewer find it. This one is the protocol for the other half, which a corpus cannot answer. Of the findings the pipeline posts on real code that nobody planted anything in, how many are worth acting on. There is no answer key for a real pull request, so the answer key is two independent readers, and the harness's job is to make their reading cheap, repeatable and cumulative.

The moving parts:

- `backend/tests/precision/pull_requests.json` pins the set: the eleven v1.2 pull requests of this repository, 23 to 33, each by base and head sha, with the file count and the selected-file count a regenerated diff has to reproduce.
- `backend/tests/precision/judgements.json` is the ledger: two verdicts per finding, keyed by a fingerprint of the path, the title and the evidence, so a finding judged once is never judged again and a round only pays for what is new.
- `backend/scripts/precision.py` runs it: `run`, `sheet`, `merge`, `score` and `replay`.

## The question a judge answers

Would a competent maintainer change anything because of this finding?

Not "is it true", not "is it interesting", and not "is the category right". A finding that is technically true and changes nothing is `not_real`, because the number is about whether a reader's hour was well spent. A finding that names the wrong severity or the wrong category but points at something a maintainer would fix is `real`, and the mis-severity goes in the reason line.

The unit is one finding, never a review. Three consecutive reviews of pull request 13 on the same code shared about two findings by title out of thirty (`../REVIEW_QUALITY.md`, "Two things to keep in mind while reading any of its output"), so consistency between runs is low: a review's verdict would measure the sampling, where a finding's verdict measures the finding.

## Independence

`sheet` is run once. It writes one markdown sheet and one JSON skeleton. The skeleton is copied once per judge, each judge fills their own copy without reading the other's, and `merge` is the first moment the two meet. `merge` refuses anything that is not exactly two verdicts from two distinct judge identities, so a round cannot quietly become one reader twice.

A judge reads the finding, the evidence, the diff context the sheet prints, and the code itself. A judge who wrote the code under judgement says so in the round's note; it is not a disqualification on a repository with one author, but it belongs beside the number.

Disagreement is recorded, not resolved. A finding the two judges split on counts as `disputed`, and disputed is not `real`: precision is the share of judged findings **both** judges called real.

## What counts as the same finding

The fingerprint is `sha256(path + normalised title + normalised evidence)`, first twelve hex characters. Normalisation forgives what a model varies without changing its claim:

- the title: case, whitespace, surrounding quotes and backticks, trailing sentence punctuation, and the kind inside a `[REDACTED:...]` marker, folded as it is in the evidence, because a model quotes a redacted line into its title too.
- the evidence: whitespace, the two quote marks folded into one (the locator already treats `args['url']` as a quote of `args["url"]`), a leading `+`, `-` or space from the diff, and the kind inside a `[REDACTED:...]` marker, since a later redaction pattern may name the same line differently. Case in the evidence is kept, because case in the evidence is the code.

The pull request number is deliberately not in the fingerprint. The same claim about the same line of the same file is one judgement wherever it recurs, so a ledger entry carries a list of the pull requests it has been seen on: `merge` stores every pull request of the round the finding was seen on, and `merge --skip-existing` adds the pull requests of a later round to an entry that already exists; the per-pull-request table in `score` is driven by the run records instead.

Two things re-fingerprint a finding that has already been judged, and `sheet` names the likely match when it sees one: the postprocess retitles a finding whose title is the prompt's own sentence from its recommendation, and it trims multi-line evidence to the one line it located. Both change the fingerprint. A judge who is shown a "possibly the same as" line should still judge the finding; the duplicate is the ledger's problem, not theirs.

## The six reason categories

A `not_real` verdict carries a category and one line of reason. The first five are the ones the 2026-09-07 reading found (`../REVIEW_QUALITY.md`, "Where the errors came from"), kept identical so the two measurements can be compared; the sixth is a catch-all whose growth is a signal that this list needs another entry.

| Category            | What it is                                                                                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `wrong_about_code`  | A claim the diff cannot settle and the code contradicts: an import called unused when it is used below the hunk, a caller called absent when it is there |
| `style_preference`  | True, no defect: a comment the model finds redundant, a name it would rather spell differently                                                           |
| `untouched_line`    | A finding about a line the pull request never touched, which is the pipeline accepting a context line as evidence                                        |
| `defence_as_attack` | A redaction pattern, a test fixture holding a hostile string or a docstring quoting an attack, read as the attack                                        |
| `instruction_title` | The title is the reviewer's own instruction copied into the slot rather than a problem                                                                   |
| `other`             | None of the five; the reason line carries the weight                                                                                                     |

No example above names a finding of any round, on purpose: a judge reads this file before judging, and a worked example of a real finding in a category is a vote cast before the reading starts. The votes are per judgement, not per finding, so one finding can carry two different categories, one from each judge, and the vote total of a round is twice its judged count.

## The size of the set, stated plainly

"Eleven real pull requests" oversells the denominator, so here is what the eleven are:

- PRs 23 and 32 contribute nothing at all. Every file they change is markdown, skipped as "not code" (`SKIP_LANGUAGES` in `backend/services/review_runner.py`), so no model call is made.
- PRs 25, 27 and 33 were reviewed (5, 10 and 2 files) and produced no findings.
- All 22 of round 0's findings came from the remaining six: 24, 26, 28, 29, 30 and 31.

So a round's number rests on six pull requests. Of the 109 files the eleven change, 64 are selected for review, and on the 2026-09-07 night 63 of those came back with a usable review (PR 24's `backend/tests/test_runner.py` answered unreadably and is recorded as errored, not skipped). That is the honest size, and it is why the closing note below matters.

## The conditions round 0 reproduces

Round 0 is the 2026-09-07 night, quoted from `../REVIEW_QUALITY.md`: `qwen3.5:9b` reviewing, `gemma4:12b` cross-examining, sequentially, `VERIFY_FINDINGS` off, `MAX_FILES_PER_REVIEW` 50, 16k context. `MAX_FILES_PER_REVIEW` at its shipped default of 25 reproduces that selection exactly, because the largest eligible set in the eleven is 16 files, so the default is what the harness runs at.

Round 0 is built with no model at all: `run --from-database` reads the 22 findings the night stored, through one read-only immutable SQLite URI, and regenerates each patch from git so a judge sees the lines the model saw. That the regenerated diff is the diff the model was shown is measured rather than assumed, by tests in `backend/tests/test_precision.py`: the split three-dot diff reproduces the recorded file count and the recorded selection for all eleven, and all 22 stored findings still locate on the exact line the database recorded.

Two things follow, and both are limits on how round 0 may be read.

The night's own 44 judgements are gone; only the aggregate table survives. Round 0's ledger is therefore a 2026-09-12 re-judgement of the same 22 findings, not a transcription of the old one, and its number may differ from the 0 of 22 written down then.

Round 0 is a judged snapshot of a pipeline that has since moved. The instruction-title retitle rule landed the same night, so some of the 22 would not survive today's postprocess unchanged. The first like-for-like pair is therefore round 1 against round 1 replayed, not round 1 against round 0.

## Running a round

From `backend/` with the venv. Only the first command needs Ollama.

```
.venv/bin/python scripts/precision.py run --out ~/ReviewBot-runs/<date>/precision-runs --tag round1 \
    --model qwen3.5:9b --cross-model gemma4:12b --unload
.venv/bin/python scripts/precision.py sheet ~/ReviewBot-runs/<date>/precision-runs round1 --out ~/ReviewBot-runs/<date>
cp ~/ReviewBot-runs/<date>/round1-skeleton.json ~/ReviewBot-runs/<date>/round1-judge-a.json
cp ~/ReviewBot-runs/<date>/round1-skeleton.json ~/ReviewBot-runs/<date>/round1-judge-b.json
# each judge fills their own copy, without reading the other's
.venv/bin/python scripts/precision.py merge ~/ReviewBot-runs/<date>/round1-judge-a.json ~/ReviewBot-runs/<date>/round1-judge-b.json
.venv/bin/python scripts/precision.py score ~/ReviewBot-runs/<date>/precision-runs round1
mkdir -p ../docs/benchmarks/runs/<date>
.venv/bin/python scripts/precision.py score ~/ReviewBot-runs/<date>/precision-runs round1 --markdown \
    > ../docs/benchmarks/runs/<date>/precision-round1.md
```

The records hold real code and every raw model reply, so they stay outside the repository under `~/ReviewBot-runs/<date>/precision-runs/`, the same rule as the prompt runs; `run` refuses an `--out` inside the working tree. What is committed is the ledger and the round's row. While any finding is unjudged `score` prints `partial (N of M judged)` where the precision would be, `--markdown` says so in a line above the table, and both exit 2, so a partial ledger cannot quietly become a published figure.

A pipeline change is measured with no model at all:

```
.venv/bin/python scripts/precision.py replay ~/ReviewBot-runs/<date>/precision-runs round1 \
    --out ~/ReviewBot-runs/<date>/precision-runs --tag-out round1-after
```

`replay` pushes the round's recorded replies back through the current pipeline, carries the judgements by fingerprint, and prints the number before and after. A change that only removes findings needs no new judging, because everything it removes is already judged. A change that produces a finding nobody has judged gets a best case and a worst case, and `replay` exits 2 unless that bound already settles the question.

## The time budget

| Step                                | Cost                                                                                                                          |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `run`, reviewer and cross           | About 45 minutes of laptop: the eleven took 2,539 seconds on 2026-09-07, plus about four minutes of model loads in two phases |
| `run`, reviewer alone               | About 20 minutes                                                                                                              |
| `run --from-database`               | Seconds, no model                                                                                                             |
| Two judges over 20 to 30 findings   | About an hour each                                                                                                            |
| `sheet`, `merge`, `score`, `replay` | Seconds, no model, and they run with the machine busy                                                                         |

The machine conditions for the `run` step are the ones in [HOW_TO_RUN_A_ROUND.md](HOW_TO_RUN_A_ROUND.md): one model resident at a time, the dashboard tab closed, on mains.

## Rounds

Each round's row is also written to `runs/<date>/precision-<tag>.md` by `score --markdown`, so the day tables in [README.md](README.md) keep meaning one measurement day, and the rolling comparison lives here.

| Round  | Date       | Model                          | Findings | Distinct | Judged | Real | Disputed | Precision |
| ------ | ---------- | ------------------------------ | -------- | -------- | ------ | ---- | -------- | --------- |
| round0 | 2026-09-12 | `qwen3.5:9b` plus `gemma4:12b` | 22       | 22       | 22     | 0    | 1        | 0.00      |

Round 0 was judged on 2026-09-12 by two Claude sessions (`claude-opus-5/judge-a` and `claude-opus-5/judge-b`) with no shared context, each reading the sheet and the code at the pull request's head. Both called 21 of the 22 not real; they split on one, a `logger.error` in the nightly retention loop that keeps the exception's type and drops its message and traceback, which one judge would fix with `logger.exception` and the other left alone as the codebase's deliberate logging convention. The votes: real 1, wrong about the code 16, style preference 15, defence as attack 3, instruction title 2, untouched line 2, other 5. The row is `runs/2026-09-12/precision-round0.md`.

## A note on the error bar

At 22 findings a round's precision moves by 4.5 points per finding, and the judged set rests on six pull requests. A difference of a few points between two rounds is noise, and a round that produces a handful of findings says little about a model. What the number is for is the direction of a deliberate change, measured the same way twice, with `replay` rather than a fresh round wherever the change is in the pipeline rather than in the model. Read it beside the recall tables, never instead of them: high recall on planted bugs and low precision on careful, already reviewed diffs are both true at once, and they measure different things.
