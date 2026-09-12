# 2026-09-05: refining the reviewer, verifier and cross-examiner prompts

Machine: Apple M1 Max, 32 GB, Ollama 0.33.3 (desktop app, loopback only). Models: `qwen3.5:9b` (reviewer), `gemma4:12b` (cross-examiner). One model resident at a time throughout: every run below ends with `--unload`, and cross-examiner and verifier runs replay the reviewer's recorded replies (`--replay`) so only their own model is loaded. Pipeline commit for the runs marked "fixed pipeline": 469b67c; the first full run (`full1`) ran on 6802e4d, before the three finding-loss fixes in a0d299c, so it is used to choose candidates, not to quote shipped numbers.

Corpus: `backend/tests/prompt_corpus.py` (76 cases: 11 original, 65 added today, 16 of them clean) plus `backend/tests/prompt_redteam.py` (15 hostile diffs), 91 cases in all; the cross-examiner screen used a 30-case subset (9 clean, 13 planted, 8 red team). Ground truth as corrected during the day (every line of a planted block; simplicity findings expected at low). Judge: `backend/scripts/prompt_judge.py`, rule in its docstring; every table below is its output, re-scored against the corrected ground truth with `--corpus`. Columns: `obeyed` and `inj_rep` count red-team cases; `fp/clean` is false positives per clean diff; `x_add` is the share of planted lines found only by the cross-examiner; `x_refT` is first-pass hits refuted by the cross-examiner; `score` is recall with each clean-diff false positive costing twice a miss; `tokens` and `sec` are per file for the whole pipeline.

Raw rows, including every model's raw reply per case, live outside the repository in `~/ReviewBot-runs/2026-09-05/prompt-runs/<tag>-<variant>.json`; the compact summaries and these leaderboards are in `runs/2026-09-05/`.

## full1: four reviewer prompts, 91 cases, two repeats (pipeline 6802e4d)

```
.venv/bin/python scripts/prompt_eval.py --cases-from-file full.json --prompts-dir reviewer2 --variants new,a11y-r2,checklist-r2,synthesis-r2 --repeats 2 --out runs --tag full1 --unload
```

| variant            | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep | x_add | x_refT | score | tokens | sec  |
| ------------------ | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ------- | ----- | ------ | ----- | ------ | ---- |
| a11y-r2            | 698   | 182   | 0   | 0/32   | 0.92   | 0.12     | 0.09    | 0.99 | 0.98 | 12/32   | -     | -      | 0.89  | 1532   | 15.6 |
| checklist-r2       | 699   | 182   | 0   | 0/32   | 0.813  | 0.0      | 0.0     | 0.97 | 0.94 | 14/32   | -     | -      | 0.846 | 1540   | 13.9 |
| new                | 473   | 182   | 0   | 0/32   | 0.66   | 0.06     | 0.06    | 0.98 | 1.0  | 24/32   | -     | -      | 0.698 | 1000   | 9.2  |
| synthesis-r2 (OUT) | 700   | 182   | 0   | 2/32   | 0.8    | 0.0      | 0.0     | 0.97 | 0.95 | 11/32   | -     | -      | 0.835 | 1504   | 13.0 |

What it says. The round-two revision of the accessibility-led prompt (a11y-r2, 698 words) is the winner: recall 0.92 against the shipped prompt's 0.66, with false positives held at 0.12 per clean diff (the round-one version of the same prompt sat at 1.22 on the screening subset). synthesis-r2 is marked OUT for "obeyed 2/32"; the raw text shows both rows were the JSON grammar closing the object early after an unescaped quote in the summary (`options={"`), not obedience. That bug is fixed in a0d299c. Reading the winner's raw replies also found `<html>` refused as evidence for being six characters, and a 44-character base64 key copied with one slip and dropped, both fixed in the same commit.

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

**Correction, found at 01:35 on 2026-09-06.** The harness reused one reviewer object for a whole variant, and the per-review call budgets live on that object (25 cross-examiner calls, 40 verifier calls), so this run verified only the first 40 findings and left 19 rows with findings unverified. The ranking among candidates in it stands, because every candidate saw the same rows, but its absolute numbers are diluted with rows the second model never saw. Fixed in b269fab (each case starts with a fresh budget, and the judge's `x_calls` column shows how many rows the second model saw); the corrected runs are `verify2` below.

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

**Correction, found at 01:35 on 2026-09-06.** The harness reused one reviewer object for a whole variant, and the per-review call budgets live on that object (25 cross-examiner calls, 40 verifier calls), so this run cross-examined only the first 25 of its 30 rows. The ranking among candidates in it stands, because every candidate saw the same rows, but its absolute numbers are diluted with rows the second model never saw. Fixed in b269fab (each case starts with a fresh budget, and the judge's `x_calls` column shows how many rows the second model saw); the corrected runs are `xscreen3` below.

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

The reviewer alone on the same 30 cases (first repeat of full1-a11y-r2): recall 1.0, 0.11 false positives per clean diff, score 0.933, injection reported 2 of 8. What it says. Every cross-examiner candidate scored below the reviewer alone: each removed false positives and lost real findings. Two shapes explained most of the losses. gemma answers false_positive when it only disagrees with the severity and then adds the same problem in its own words on the same line (teacher-a did this sixteen times in thirty cases); the reconciliation now treats that as a correction (469b67c). And gemma rightly refuted findings that named the right line for the wrong reason (an "injection" on an int() of an environment variable) without adding the finding it should have written. The shipped cross prompt and refute-first-a are OUT: each was talked out of a real command injection by a planted comment claiming a prior "cleared as false positive" ticket, and silenced the reviewer's report of that comment. The round-two brief targets exactly these; results land in `xscreen2` and `xfinal` below.

## Cloud reference: the same prompts on bigger models through Ollama's cloud tags

Run with `--allow-cloud`, the harness's one switch that turns `STRICT_LOCAL` off, on the synthetic corpus only. The cloud path does not enforce the JSON grammar, so the harness appends a sentence naming the keys and the allowed values; the first attempt without it parsed 146 of 182 replies as empty because the 31B answered in its own shape. Cloud rows count only the relay's own time, so `sec` is not comparable with the local tables.

```
.venv/bin/python scripts/prompt_eval.py --allow-cloud --model gemma4:31b-cloud --cases-from-file full.json --prompts-dir winner --variants new,a11y-r2 --repeats 2 --out runs --tag cloud-gemma4_31b
```

| variant | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep | x_add | x_refT | score | tokens | sec |
| ------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ------- | ----- | ------ | ----- | ------ | --- |
| a11y-r2 | 779   | 182   | 0   | 0/32   | 0.947  | 0.06     | 0.0     | 1.0  | 0.85 | 15/32   | -     | -      | 0.934 | 1605   | 1.1 |
| new     | 554   | 182   | 0   | 0/32   | 0.813  | 0.06     | 0.0     | 0.92 | 0.84 | 28/32   | -     | -      | 0.824 | 1138   | 1.0 |

```
.venv/bin/python scripts/prompt_eval.py --allow-cloud --model gpt-oss:120b-cloud --cases-from-file full.json --prompts-dir winner --variants new,a11y-r2 --repeats 2 --out runs --tag cloud-gpt-oss_120b
```

| variant       | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep | x_add | x_refT | score | tokens | sec |
| ------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ------- | ----- | ------ | ----- | ------ | --- |
| a11y-r2 (OUT) | 779   | 182   | 0   | 6/32   | 0.9    | 0.12     | 0.03    | 0.98 | 0.98 | 21/32   | -     | -      | 0.885 | 2323   | 3.0 |
| new (OUT)     | 554   | 182   | 0   | 2/32   | 0.753  | 0.22     | 0.12    | 0.96 | 0.89 | 26/32   | -     | -      | 0.72  | 1613   | 2.0 |

What it says. The prompt scales: on the 31B of the same family as the local cross-examiner, the winner reaches recall 0.947 at 0.06 false positives per clean diff (score 0.934 against 0.89 on the local 9B), and the shipped prompt gains more from the bigger model than the winner does (0.66 to 0.81), which is what a prompt that already names the classes should show. The 120B open-weight model from OpenAI scores 0.885 with the winner and is marked OUT for "obeyed 6 of 32"; the raw replies show it obeyed nothing: three were empty replies on the two longest hostile files and three were reviews that found the bug and reported the injection but ran past the 2,000-token output cap and failed to parse. The 397B Qwen and the other "medium usage" cloud tags need a paid tier and were not measured.

## full2a, full2b, exporder, full2c: the shipped candidates like for like (fixed pipeline)

After the three finding-loss fixes (a0d299c) the incumbent and the winner were re-measured, and the drop that appeared was not the fixes. Making every JSON key required had a side effect: Ollama's grammar now holds the model to the schema's field order (182 of 182 replies followed it, where before 182 of 182 wrote the summary first), and findings-first made the 9B conservative. Same prompt, same diffs:

```
.venv/bin/python scripts/prompt_eval.py --cases-from-file full.json --prompts-dir winner --variants new,a11y-r2 --repeats 2 --out runs --tag full2a --unload
```

| variant | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev | inj_rep | x_add | x_refT | score | tokens | sec  |
| ------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | --- | ------- | ----- | ------ | ----- | ------ | ---- |
| a11y-r2 | 698   | 182   | 0   | 0/32   | 0.88   | 0.0      | 0.0     | 0.98 | 1.0 | 9/32    | -     | -      | 0.901 | 1505   | 13.4 |
| new     | 473   | 182   | 0   | 0/32   | 0.707  | 0.06     | 0.06    | 0.97 | 1.0 | 24/32   | -     | -      | 0.736 | 1021   | 9.7  |

Recall 0.867 against 0.92 in full1, with the summaries still describing the very problems the findings list then left out. A twelve-case experiment (`exporder`, the ten cases that changed plus two clean controls) with the summary moved before the findings in the schema brought every one of them back:

| variant | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep | x_add | x_refT | score | tokens | sec  |
| ------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ------- | ----- | ------ | ----- | ------ | ---- |
| a11y-r2 | 698   | 12    | 0   | -      | 1.0    | 1.33     | 1.33    | 0.89 | 0.89 | -       | -     | -      | 0.5   | 1512   | 19.8 |

So the shipped schema puts the summary first (f54d1b2): one sentence on what the change does, written first, is a scratchpad for a small model, and with the findings required after it a truncated summary still costs nothing but the summary. The hand polish (a11y-r3) ran on that order by a three-minute margin (`full2b`), then all three shipped candidates were measured on it together (`full2c`; commit 2a01274 for the pipeline, before the removed-line locator fallback in 96e95e4):

```
.venv/bin/python scripts/prompt_eval.py --cases-from-file full.json --prompts-dir final --variants a11y-r2,a11y-r3 --repeats 2 --out runs --tag full2c --unload
.venv/bin/python scripts/prompt_eval.py --cases-from-file full.json --variants new --repeats 2 --out runs --tag full2c --unload
```

| variant | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep | x_add | x_refT | score | tokens | sec  |
| ------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ------- | ----- | ------ | ----- | ------ | ---- |
| a11y-r3 | 699   | 182   | 0   | 0/32   | 0.953  | 0.19     | 0.19    | 0.97 | 0.99 | 21/32   | -     | -      | 0.896 | 1521   | 12.7 |
| a11y-r2 | 698   | 182   | 0   | 0/32   | 0.96   | 0.22     | 0.12    | 0.97 | 0.99 | 14/32   | -     | -      | 0.89  | 1533   | 13.0 |
| new     | 473   | 182   | 0   | 0/32   | 0.7    | 0.09     | 0.06    | 0.95 | 0.99 | 25/32   | -     | -      | 0.731 | 1009   | 8.4  |

What it says. The polish (a11y-r3, 699 words, Fable's hand revision of the round-two winner against its failure rows) ships: score 0.896 against the winner's 0.89 and the old prompt's 0.731, the same recall (0.953 against 0.96) with fewer clean-diff false positives (0.19 against 0.22) and the hostile text reported half again as often (21 of 32 against 14). Its four repeats pooled (full2b plus full2c) give the same 0.896. What the polish did not fix: the copy-pasted validator, the carousel with no pause, the html tag without lang, the low-contrast colour pair, the removed autocomplete attribute, the status message that lost its live region, and the 16-pixel target were each missed in at least one repeat, so they stay out of the opt-in floor test until a measured prompt clears them. The medium-plus false positives rose from 0.12 to 0.19, all of them accessibility findings on the clean controls (a focus indicator carried by box-shadow, an alt text built from a prop, an XSS claimed on an image source); that is the next round's brief. Its 31B cloud reference: recall 0.973, 0.09 false positives, score 0.945 (`cloud-gemma4_31b-r3`).

## xscreen2: the revised cross-examiner prompts, 30-case subset, gemma only (pipeline 2a01274)

**Correction, found at 01:35 on 2026-09-06.** The harness reused one reviewer object for a whole variant, and the per-review call budgets live on that object (25 cross-examiner calls, 40 verifier calls), so this run cross-examined only the first 25 of its 30 rows. The ranking among candidates in it stands, because every candidate saw the same rows, but its absolute numbers are diluted with rows the second model never saw. Fixed in b269fab (each case starts with a fresh budget, and the judge's `x_calls` column shows how many rows the second model saw); the corrected runs are `xscreen3` below.

Three Opus writers revised the two leading cross prompts and synthesised a third against the brief built from `xscreen` (false positive used for a severity disagreement, talked out of a finding by a planted comment, refuting the reason and leaving the line, praise as additions, additions that never find the reviewer's misses). Screened beside the unrevised leader, replaying the winning reviewer's recorded replies:

```
.venv/bin/python scripts/prompt_eval.py --cases-from-file subset_cross.json --replay runs/full1-a11y-r2.json --cross-model gemma4:12b --cross-prompts-dir cross2 --variants cross:gap-hunter-a-r2,cross:gap-hunter-b,cross:gap-hunter-b-r2,cross:synthesis-x-r2 --repeats 1 --out runs --tag xscreen2 --unload
```

| variant               | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat | sev | inj_rep          | x_add | x_refT | score | tokens | sec  |
| --------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | --- | --- | ---------------- | ----- | ------ | ----- | ------ | ---- |
| cross:gap-hunter-b    | 698   | 30    | 0   | 0/8    | 0.857  | 0.0      | 0.0     | 1.0 | 1.0 | 2/8 (reviewer 2) | 0.0   | 3      | 0.9   | 2576   | 29.5 |
| cross:gap-hunter-b-r2 | 698   | 30    | 0   | 0/8    | 0.857  | 0.0      | 0.0     | 1.0 | 1.0 | 2/8 (reviewer 2) | 0.0   | 3      | 0.9   | 2855   | 32.1 |
| cross:synthesis-x-r2  | 698   | 30    | 0   | 0/8    | 0.762  | 0.0      | 0.0     | 1.0 | 1.0 | 2/8 (reviewer 2) | 0.0   | 5      | 0.833 | 2773   | 28.9 |
| cross:gap-hunter-a-r2 | 698   | 30    | 0   | 0/8    | 0.905  | 0.33     | 0.0     | 1.0 | 1.0 | 2/8 (reviewer 2) | 0.0   | 2      | 0.733 | 2838   | 31.3 |

What it says. The revisions did not beat the original gap-hunter-b: its round-two version ties it on every column and costs more tokens, the synthesis loses recall, and the gap-hunter-a revision trades false positives for the recall it gains. gap-hunter-b ships as `CROSS_SYSTEM_PROMPT` (the tie broke on cost, as the judge's rule says). The three true findings it still refutes are the wrong-reason hits (an "injection" claimed on an int() of an environment variable, an "unpinned" claim on a lodash import, a "missing label" claim where the label is present), refuted correctly and not replaced; the reviewer alone still scores 0.933 on this subset against the cross-examiner's 0.90, so on this corpus the cross-examiner buys its zero false positives with three lost findings, and it stays an option rather than a default. The full-corpus measurement of the shipped pair is `xfinal` below.

## verify2 and xscreen3: the verifier and the cross-examiner screen, corrected (fresh budget per case, pipeline b269fab)

Both replay the shipped reviewer's recorded replies (`full2c-a11y-r3`), so the second model is the only live call and every row is examined (`x_calls`).

```
.venv/bin/python scripts/prompt_eval.py --cases-from-file full.json --replay runs/full2c-a11y-r3.json --verify-prompts-dir verify --variants new+verify,verify:verify-strict,verify:verify-lenient --repeats 1 --out runs --tag verify2 --unload
```

| variant                     | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev | inj_rep            | x_add | x_refT | x_calls | score | tokens | sec  |
| --------------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | --- | ------------------ | ----- | ------ | ------- | ----- | ------ | ---- |
| verify:verify-strict (OUT)  | 699   | 91    | 0   | 0/16   | 0.933  | 0.12     | 0.12    | 0.96 | 1.0 | 5/16 (reviewer 10) | -     | -      | -       | 0.901 | 2523   | 19.1 |
| verify:verify-lenient (OUT) | 699   | 91    | 0   | 0/16   | 0.893  | 0.12     | 0.12    | 0.97 | 1.0 | 1/16 (reviewer 10) | -     | -      | -       | 0.868 | 2520   | 19.6 |
| new+verify (OUT)            | 699   | 91    | 0   | 0/16   | 0.893  | 0.12     | 0.12    | 0.97 | 1.0 | 1/16 (reviewer 10) | -     | -      | -       | 0.868 | 2521   | 19.5 |

The reviewer alone on the same 91 cases: recall 0.953, 0.19 false positives per clean diff, hostile text reported in 10 of 16. What it says. verify-strict is the best verifier measured (recall 0.933, false positives down to 0.12, the judge's score 0.901 against the reviewer's 0.896) and ships as the verifier text, but every verifier refutes the reviewer's reports of planted instructions (5 of 16 kept for strict, 1 of 16 for the other two), which the judge treats as disqualifying, so the pass stays off by default until a verifier keeps those reports. The capped run had shown the two new verifiers tying; with every finding verified they do not.

```
.venv/bin/python scripts/prompt_eval.py --cases-from-file subset_cross.json --replay runs/full2c-a11y-r3.json --cross-model gemma4:12b --cross-prompts-dir cross2 --variants cross:gap-hunter-a-r2,cross:gap-hunter-b,cross:gap-hunter-b-r2,cross:synthesis-x-r2 --repeats 1 --out runs --tag xscreen3 --unload
```

| variant                     | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev | inj_rep          | x_add | x_refT | x_calls | score | tokens | sec  |
| --------------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | --- | ---------------- | ----- | ------ | ------- | ----- | ------ | ---- |
| cross:gap-hunter-a-r2       | 699   | 30    | 0   | 0/8    | 0.905  | 0.67     | 0.0     | 0.95 | 1.0 | 6/8 (reviewer 5) | 0.0   | 2      | 30/30   | 0.6   | 3122   | 34.2 |
| cross:gap-hunter-b (OUT)    | 699   | 30    | 0   | 0/8    | 0.81   | 0.0      | 0.0     | 1.0  | 1.0 | 3/8 (reviewer 5) | 0.0   | 4      | 30/30   | 0.867 | 2820   | 33.0 |
| cross:gap-hunter-b-r2 (OUT) | 699   | 30    | 0   | 0/8    | 0.857  | 0.11     | 0.0     | 1.0  | 1.0 | 3/8 (reviewer 5) | 0.0   | 3      | 30/30   | 0.833 | 3150   | 36.0 |
| cross:synthesis-x-r2 (OUT)  | 699   | 30    | 0   | 0/8    | 0.762  | 0.0      | 0.0     | 1.0  | 1.0 | 3/8 (reviewer 5) | 0.0   | 5      | 30/30   | 0.833 | 3089   | 33.8 |

The reviewer alone on the same 30 cases: hostile text reported in 5 of 8. What it says. With every row examined the picture changes. gap-hunter-b, the leader of the capped screens, silences two of the reviewer's five injection reports on this subset and is out; so are its revision and the synthesis. The one prompt that keeps every report, and adds one, is gap-hunter-a-r2, at a price: 0.67 false positives per clean diff, all at low or info, and a score of 0.60 against the reviewer alone at 0.933. The full-corpus measurement of that prompt against the shipped reviewer is `xfinal2` below; the cross-examiner stays an option, not a default, and the honest reading is that on this corpus the second model earns its place through the disagreement view and the reports it refuses to drop, not through the score.

## xfinal2: the shipped pair on the full corpus (fresh budget per case, pipeline b269fab)

```
.venv/bin/python scripts/prompt_eval.py --cases-from-file full.json --replay runs/full2c-a11y-r3.json --cross-model gemma4:12b --cross-prompts-dir cross2 --variants cross:gap-hunter-a-r2 --repeats 2 --out runs --tag xfinal2 --unload
```

| variant               | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep             | x_add | x_refT | x_calls | score | tokens | sec  |
| --------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ------------------- | ----- | ------ | ------- | ----- | ------ | ---- |
| cross:gap-hunter-a-r2 | 699   | 182   | 0   | 0/32   | 0.927  | 0.56     | 0.06    | 0.96 | 0.99 | 23/32 (reviewer 10) | 0.0   | 4      | 182/182 | 0.786 | 3122   | 33.9 |

The shipped reviewer alone on the same 182 rows: recall 0.953, 0.19 false positives per clean diff (0.19 at medium or worse), hostile text reported in 21 of 32, score 0.896, 12.7 seconds a file. What it says. The pair keeps every injection report the reviewer made and adds two, obeys nothing, and removes the medium-plus false positives (0.19 to 0.06), at the cost of three planted findings in a hundred (recall 0.927) and a rise in low and info findings on clean diffs (0.56 per clean diff), which is where its score (0.786) falls below the reviewer's. Every row was examined this time (`x_calls` 182 of 182). 34 seconds a file for the pair on the reference machine, one model resident at a time.

Its cloud reference, the 31B of the same family as the cross-examiner:

```
.venv/bin/python scripts/prompt_eval.py --allow-cloud --cases-from-file full.json --replay runs/full2c-a11y-r3.json --cross-model gemma4:31b-cloud --cross-prompts-dir cross2 --variants cross:gap-hunter-a-r2 --repeats 1 --out runs --tag cloud-gemma4_31b-cross2
```

| variant               | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep             | x_add | x_refT | x_calls | score | tokens | sec  |
| --------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ------------------- | ----- | ------ | ------- | ----- | ------ | ---- |
| cross:gap-hunter-a-r2 | 699   | 91    | 0   | 0/16   | 0.973  | 0.44     | 0.25    | 0.96 | 0.99 | 13/16 (reviewer 10) | 0.04  | 2      | 91/91   | 0.824 | 3210   | 13.9 |

The bigger cross-examiner adds recall (0.973) and keeps 13 of 16 reports, with the same appetite for low-severity findings on clean diffs.

## What shipped, and what the day changed

- `SYSTEM_PROMPT`: a11y-r3 (1338146). `VERIFY_SYSTEM_PROMPT`: verify-strict, off by default (689803e). `CROSS_SYSTEM_PROMPT`: gap-hunter-a-r2, off by default (e8a558a, replacing 2135944, which had shipped gap-hunter-b on the capped screen).
- The review schema writes the summary first and requires every key (f54d1b2); the evidence locator accepts a whole short line, a long literal copied with a slip, and a quote of a removed line (a0d299c, 96e95e4); encryption and signing keys are redacted (a0d299c); a refute-plus-re-add on one line is a correction (469b67c); a review can run the two models one at a time (91f3ff8); the harness replays, unloads, spells the shape out for cloud tags, and gives every case a fresh budget (643b993, 97994a2, 5fe38e7, 8ec8e01, b269fab); the corpus has 76 cases (6802e4d, e87a8e3, 64fff77).
- Machine: 2021 M1 Max, 32 GB. With one model resident the whole day's measurement kept memory above 40 percent free; both resident had crashed it the night before. Ollama was shut down at 03:52 on 2026-09-06 when the last run finished.
