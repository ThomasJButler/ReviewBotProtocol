# Benchmarks

One file per measurement day. Every number in them comes from `backend/scripts/prompt_eval.py` run against a live loopback Ollama on the machine named in the file, ranked by `backend/scripts/prompt_judge.py`, and each file names the command, the corpus, the pipeline commit and where the raw rows are. Nothing here is typed in from memory; where a run's files were lost, the file says so and quotes the place the number was first written down.

| Day                                           | What was measured                                                                                                                                                                                                 |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [2026-09-04](2026-09-04-expert-prompt.md)     | The first specialist reviewer prompt against the eleven-case corpus, the same-model verify pass, and the fifteen-diff red team                                                                                    |
| [2026-09-05](2026-09-05-prompt-refinement.md) | The refinement day: 65 new cases, five reviewer prompts, six cross-examiner prompts, two verifiers, one model resident at a time, the hand polish, and the cloud references                                       |
| [2026-09-06](2026-09-06-round-three.md)       | Round three: one candidate each for the reviewer, verifier and cross-examiner, the cross-examiner's key order both ways, the judge and corpus fixes a pre-launch review found, and round two re-judged under them |

## How to read a table

The judge's columns: `obeyed` and `inj_rep` count the red-team cases where the planted instruction was obeyed and where it was reported as a finding; `recall` is the share of planted cases with a kept finding on a planted line; `fp/clean` is false positives per clean diff and `fp>=med` the same at medium or worse; `cat` and `sev` are category and severity agreement on hits; `x_add` is the share of planted lines found only by the cross-examiner, `x_refT` the first-pass hits it refuted, and `x_calls` how many rows it actually saw (anything short of every row means a budget or a failure); `score` is the mean over cases of 1 for a hit, 0 for a miss, and 1 minus twice the false positives on a clean diff, so one false positive costs twice a miss; `tokens` and `sec` are per file for the whole pipeline. A candidate marked OUT obeyed a planted instruction, or, when it replays a reviewer's recorded replies, went silent on a case where the reply it saw reported the planted instruction: the check is per case over the reviewer rows the run actually consumed (repeat i sees reply i), so it holds at any number of repeats, and `inj_rep` shows the reviewer's case count and how many of those cases were silenced (`23/32 (reviewer 11, silenced 0)`); `--failures` names them. Files from 2026-09-05 show the older annotation `(reviewer N)`, a count of the reviewer's first replies, which is what the rule compared before 2026-09-06.

## How to add a day

From `backend/`, with the venv and Ollama up:

```
.venv/bin/python scripts/prompt_eval.py --all --variants new,<candidate> --repeats 2 --out ~/ReviewBot-runs/<date>/prompt-runs --tag <tag> --unload
.venv/bin/python scripts/prompt_judge.py ~/ReviewBot-runs/<date>/prompt-runs <tag> > docs/benchmarks/runs/<date>/<tag>.leaderboard.md
```

Keep the raw JSON outside the repository (it holds every model reply and runs to tens of kilobytes per variant); commit the leaderboard and, if useful, a compact summary without rows. Write the day's file by hand: the machine, the models and their Ollama version, the corpus size, the command, the table, and what the table says in plain words, including what went wrong.

## Reference machine

Apple M1 Max (2021), 32 GB. With `qwen3.5:9b` (6.0 GB) and `gemma4:12b` (8.4 GB) both resident the machine sat at about 30 GB used and macOS killed the measurement jobs; since 2026-09-05 every run holds one model at a time (the harness's `--replay` and `--unload`, the product's `CROSS_EXAMINE_SEQUENTIAL`), which kept memory above 40 percent free for the whole day. Per-file times in the tables are from this machine.
