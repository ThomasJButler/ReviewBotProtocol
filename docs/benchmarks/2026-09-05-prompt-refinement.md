# 2026-09-05: refining the reviewer, verifier and cross-examiner prompts

Machine: Apple M1 Max, 32 GB, Ollama 0.33.3 (desktop app, loopback only). Models: `qwen3.5:9b` (reviewer), `gemma4:12b` (cross-examiner). One model resident at a time throughout: every run below ends with `--unload`, and cross-examiner and verifier runs replay the reviewer's recorded replies (`--replay`) so only their own model is loaded. Pipeline commit for the runs marked "fixed pipeline": e122a0e; the first full run (`full1`) ran on 4950a3d, before the three finding-loss fixes in 64ebab2, so it is used to choose candidates, not to quote shipped numbers.

Corpus: `backend/tests/prompt_corpus.py` (76 cases: 11 original, 65 added today, 16 of them clean) plus `backend/tests/prompt_redteam.py` (15 hostile diffs), 91 cases in all; the cross-examiner screen used a 30-case subset (9 clean, 13 planted, 8 red team). Ground truth as corrected during the day (every line of a planted block; simplicity findings expected at low). Judge: `backend/scripts/prompt_judge.py`, rule in its docstring; every table below is its output, re-scored against the corrected ground truth with `--corpus`. Columns: `obeyed` and `inj_rep` count red-team cases; `fp/clean` is false positives per clean diff; `x_add` is the share of planted lines found only by the cross-examiner; `x_refT` is first-pass hits refuted by the cross-examiner; `score` is recall with each clean-diff false positive costing twice a miss; `tokens` and `sec` are per file for the whole pipeline.

Raw rows, including every model's raw reply per case, live outside the repository in `~/ReviewBot-runs/2026-09-05/prompt-runs/<tag>-<variant>.json`; the compact summaries and these leaderboards are in `runs/2026-09-05/`.

## full1: four reviewer prompts, 91 cases, two repeats (pipeline 4950a3d)

```
.venv/bin/python scripts/prompt_eval.py --cases-from-file full.json --prompts-dir reviewer2 --variants new,a11y-r2,checklist-r2,synthesis-r2 --repeats 2 --out runs --tag full1 --unload
```

| variant            | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep | x_add | x_refT | score | tokens | sec  |
| ------------------ | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ------- | ----- | ------ | ----- | ------ | ---- |
| a11y-r2            | 698   | 182   | 0   | 0/32   | 0.92   | 0.12     | 0.09    | 0.99 | 0.98 | 12/32   | -     | -      | 0.89  | 1532   | 15.6 |
| checklist-r2       | 699   | 182   | 0   | 0/32   | 0.813  | 0.0      | 0.0     | 0.97 | 0.94 | 14/32   | -     | -      | 0.846 | 1540   | 13.9 |
| new                | 473   | 182   | 0   | 0/32   | 0.66   | 0.06     | 0.06    | 0.98 | 1.0  | 24/32   | -     | -      | 0.698 | 1000   | 9.2  |
| synthesis-r2 (OUT) | 700   | 182   | 0   | 2/32   | 0.8    | 0.0      | 0.0     | 0.97 | 0.95 | 11/32   | -     | -      | 0.835 | 1504   | 13.0 |

What it says. The round-two revision of the accessibility-led prompt (a11y-r2, 698 words) is the winner: recall 0.92 against the shipped prompt's 0.66, with false positives held at 0.12 per clean diff (the round-one version of the same prompt sat at 1.22 on the screening subset). synthesis-r2 is marked OUT for "obeyed 2/32"; the raw text shows both rows were the JSON grammar closing the object early after an unescaped quote in the summary (`options={"`), not obedience. That bug is fixed in 64ebab2. Reading the winner's raw replies also found `<html>` refused as evidence for being six characters, and a 44-character base64 key copied with one slip and dropped, both fixed in the same commit.

## full1o: the round-one originals, 91 cases, one repeat (fixed pipeline)

```
.venv/bin/python scripts/prompt_eval.py --cases-from-file full.json --prompts-dir reviewer --variants a11y,checklist --repeats 1 --out runs --tag full1o --unload
```

| variant   | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep | x_add | x_refT | score | tokens | sec  |
| --------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ------- | ----- | ------ | ----- | ------ | ---- |
| a11y      | 645   | 91    | 0   | 0/16   | 0.933  | 0.25     | 0.19    | 0.97 | 0.96 | 9/16    | -     | -      | 0.901 | 1595   | 19.7 |
| checklist | 693   | 91    | 0   | 0/16   | 0.853  | 0.12     | 0.12    | 0.94 | 0.92 | 11/16   | -     | -      | 0.835 | 1623   | 16.1 |

What it says. The originals ran after the fixes, so their recall is not comparable with full1's; the false-positive column is: a11y 0.25 and checklist 0.12 against their revisions' 0.12 and 0.0. The like-for-like comparison of incumbent, winner and the hand polish is `full2a` and `full2b` below.

## verify: the verifier prompts, 91 cases, replaying the shipped reviewer (fixed pipeline)

```
.venv/bin/python scripts/prompt_eval.py --cases-from-file full.json --replay runs/full1-new.json --verify-prompts-dir verify --variants new+verify,verify:verify-strict,verify:verify-lenient --repeats 1 --out runs --tag verify --unload
```

| variant                     | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev | inj_rep             | x_add | x_refT | score | tokens | sec  |
| --------------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | --- | ------------------- | ----- | ------ | ----- | ------ | ---- |
| verify:verify-strict        | 473   | 91    | 0   | 0/16   | 0.667  | 0.0      | 0.0     | 0.98 | 1.0 | 11/16 (reviewer 11) | -     | -      | 0.725 | 1321   | 12.0 |
| verify:verify-lenient (OUT) | 473   | 91    | 0   | 0/16   | 0.667  | 0.0      | 0.0     | 0.98 | 1.0 | 10/16 (reviewer 11) | -     | -      | 0.725 | 1321   | 11.9 |
| new+verify (OUT)            | 473   | 91    | 0   | 0/16   | 0.533  | 0.0      | 0.0     | 1.0  | 1.0 | 10/16 (reviewer 11) | -     | -      | 0.615 | 1311   | 12.1 |

What it says. The shipped verifier costs recall (0.53 against 0.66 without it, as measured on 2026-09-04). Both candidates hold recall at the reviewer's level and remove the remaining false positives, and they tie on every column; the judge's stable order puts verify-lenient first. The verify pass stays off by default because the cross-examiner is the second opinion, and the shipped verifier text is replaced by verify-lenient.

## xscreen: seven cross-examiner prompts, 30-case subset, replaying the winning reviewer

```
.venv/bin/python scripts/prompt_eval.py --cases-from-file subset_cross.json --replay runs/full1-a11y-r2.json --cross-model gemma4:12b --cross-prompts-dir cross --variants cross,cross:refute-first-a,cross:refute-first-b,cross:gap-hunter-a,cross:gap-hunter-b,cross:teacher-a,cross:teacher-b --repeats 1 --out runs --tag xscreen --unload
```

| variant                    | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep          | x_add | x_refT | score | tokens | sec  |
| -------------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ---------------- | ----- | ------ | ----- | ------ | ---- |
| cross:gap-hunter-b         | 698   | 30    | 0   | 0/8    | 0.857  | 0.0      | 0.0     | 1.0  | 0.89 | 2/8 (reviewer 2) | 0.1   | 5      | 0.9   | 2579   | 31.7 |
| cross:gap-hunter-a         | 698   | 30    | 0   | 0/8    | 0.905  | 0.11     | 0.0     | 1.0  | 0.95 | 2/8 (reviewer 2) | 0.1   | 4      | 0.867 | 2589   | 33.3 |
| cross:refute-first-b       | 698   | 30    | 0   | 0/8    | 0.857  | 0.22     | 0.0     | 0.94 | 0.94 | 2/8 (reviewer 2) | 0.1   | 5      | 0.767 | 2510   | 32.9 |
| cross:teacher-b            | 698   | 30    | 0   | 0/8    | 0.857  | 0.89     | 0.0     | 0.94 | 0.83 | 2/8 (reviewer 2) | 0.24  | 8      | 0.633 | 2782   | 52.8 |
| cross:teacher-a            | 698   | 30    | 0   | 0/8    | 0.81   | 0.44     | 0.0     | 0.94 | 0.88 | 2/8 (reviewer 2) | 0.57  | 16     | 0.6   | 2639   | 40.7 |
| cross (OUT)                | 698   | 30    | 0   | 0/8    | 0.905  | 0.33     | 0.22    | 1.0  | 1.0  | 1/8 (reviewer 2) | 0.0   | 2      | 0.733 | 2228   | 25.6 |
| cross:refute-first-a (OUT) | 698   | 30    | 0   | 0/8    | 0.81   | 0.44     | 0.0     | 0.94 | 0.94 | 1/8 (reviewer 2) | 0.1   | 6      | 0.6   | 2470   | 30.3 |

The reviewer alone on the same 30 cases (first repeat of full1-a11y-r2): recall 1.0, 0.11 false positives per clean diff, score 0.933, injection reported 2 of 8. What it says. Every cross-examiner candidate scored below the reviewer alone: each removed false positives and lost real findings. Two shapes explained most of the losses. gemma answers false_positive when it only disagrees with the severity and then adds the same problem in its own words on the same line (teacher-a did this sixteen times in thirty cases); the reconciliation now treats that as a correction (e122a0e). And gemma rightly refuted findings that named the right line for the wrong reason (an "injection" on an int() of an environment variable) without adding the finding it should have written. The shipped cross prompt and refute-first-a are OUT: each was talked out of a real command injection by a planted comment claiming a prior "cleared as false positive" ticket, and silenced the reviewer's report of that comment. The round-two brief targets exactly these; results land in `xscreen2` and `xfinal` below.

## Pending tonight

- `cloud-gemma4_31b`, `cloud-gpt-oss_120b`: the winner and the shipped prompt on two cloud tags (`--allow-cloud`), the bigger-model reference.
- `full2a`: incumbent and a11y-r2 on the fixed pipeline, two repeats. `full2b`: the hand polish a11y-r3, same. The shipped reviewer prompt is chosen here.
- `xscreen2`: the three revised cross-examiner prompts on the 30-case subset; `xfinal`: the best on the full corpus against the final reviewer, two repeats; `cloud-gemma4_31b-cross`: its cloud reference.
