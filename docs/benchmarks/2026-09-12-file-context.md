# 2026-09-12: the file beside the hunk (stub, tier one only)

This file is a stub on purpose. `FILE_CONTEXT` is built and ships off, and the two rounds that decide whether it goes on have not been run: no model has yet seen a prompt with a file listing in it. What is here is everything tier one produced, which needs no model at all. The two sections below hold the exact commands and the words **not yet run** until they are.

Machine: the reference laptop, a 2021 M1 Max with 32 GB. Pipeline: `v1.3-file-context`, working tree, uncommitted at the time of writing. Settings at the defaults except where a command says otherwise: `qwen3.5:9b`, `OLLAMA_NUM_CTX` 16384, `OLLAMA_NUM_PREDICT` 2000, `MIN_FINDING_CONFIDENCE` 0.5, `CONTEXT_LINE_FINDINGS` `drop`, `FILE_CONTEXT_LINES` 60.

## Tier one, no model: the off path is the incumbent

With the switch off nothing on the unconditional path changes except one name in the reviewer's marker alternation: `MARK_FILE`, `DIFF_DATA_FILE`, joins `DIFF_DATA_BEGIN` and `DIFF_DATA_END`, so a forged span label is defanged like a forged delimiter. The name is in the delimiters' family rather than named after the setting because that alternation runs on every patch, switch or no switch: a marker called `FILE_CONTEXT` defanged the word wherever a diff mentioned it, this repository's own configuration and `.env.example` first of all, and any finding quoting such a line was dropped as unlocated. That is a claim a replay can settle, so it was settled rather than asserted:

```
cd backend && .venv/bin/python -u scripts/prompt_eval.py \
  --cases-from-file ~/ReviewBot-runs/2026-09-06/refine/full.json \
  --replay ~/ReviewBot-runs/2026-09-07/prompt-runs/praise2-a11y-r3.json \
  --prompts-dir ~/ReviewBot-runs/2026-09-06/refine/round3/reviewer --variants a11y-r3 \
  --repeats 2 --model qwen3.5:9b --out ~/ReviewBot-runs/2026-09-12/prompt-runs --tag offpath
.venv/bin/python scripts/prompt_judge.py ~/ReviewBot-runs/2026-09-12/prompt-runs offpath \
  --corpus="$HOME/ReviewBot-runs/2026-09-06/refine/full.json" > ../docs/benchmarks/runs/2026-09-12/offpath.leaderboard.md
```

The run loads no model and generates nothing: it printed `replaying the reviewer replies of variant a11y-r3` and built no chat model, which is what the health-gate change of `v1.3-offline-review` made possible.

| Comparison                                                        | Rows | Differences in any scoring field                                                                                            |
| ----------------------------------------------------------------- | ---- | --------------------------------------------------------------------------------------------------------------------------- |
| `offpath` against `ctx-drop` (2026-09-12, the same shipped rules) | 182  | 0                                                                                                                           |
| `offpath` against `praise2-a11y-r3` (2026-09-07, as recorded)     | 182  | 8, every one of them from the two branches merged in between, listed below; plus five counters the older file does not have |

`ctx-drop` is the like-for-like control, because it is the same replay through the same pipeline one branch earlier: recall 0.98, 0.22 false positives per clean diff, 0.16 at medium or worse, 16 of 32 injections reported, none obeyed, score 0.929, on every one of the 182 rows, field for field. The eight differences against the 2026-09-07 file are the earlier branches' own measured effects, not this one's: four `kept_lines` titles that the instruction-title retitle rewrote (`practice_dep_for_one_liner`, `practice_single_caller_abstraction`, two repeats each) and two rows one finding shorter under `CONTEXT_LINE_FINDINGS=drop` (`owasp_llm_no_token_cap`, `wcag_img_alt_missing`), which is exactly the set the context-line addendum named. The five counters the older file has no column for are `dropped_context_line`, `downgraded_context_line` and `kept_context_lines` from the context-line branch, and `dropped_outside_diff` and `context_mode` from this one: `dropped_outside_diff` is 0 on every row and every row's `context_mode` is empty, as both must be with the switch off.

The leaderboard is `runs/2026-09-12/offpath.leaderboard.md`.

## Tier one, no model: what the context costs

`backend/scripts/file_context_budget.py` prices a range without a model or a network: the patch bytes, the file at the range's head, the bytes the listing would render to and the mode `services/file_context.py` would choose, at each context size. The budget is `OLLAMA_NUM_CTX` less `OLLAMA_NUM_PREDICT` less `PROMPT_OVERHEAD_TOKENS`, at 2.8 bytes a token: **36,355 bytes at 16384 and 82,230 at 32768**, for the patch and the listing together.

```
cd backend
.venv/bin/python scripts/file_context_budget.py --range v1.1.0..v1.2.0 --ctx 16384,32768
.venv/bin/python scripts/file_context_budget.py --range main...HEAD --ctx 16384,32768
```

`v1.1.0..v1.2.0`, the eleven-pull-request stack of the last release: 68 files in the range, 25 of them a review would read.

| num_ctx | whole | window | none               |
| ------- | ----- | ------ | ------------------ |
| 16384   | 13    | 2      | 10 (8 added files) |
| 32768   | 17    | 0      | 8 (8 added files)  |

| Patch size  | Files | whole/window/none at 16k | whole/window/none at 32k |
| ----------- | ----- | ------------------------ | ------------------------ |
| under 2 KB  | 9     | 5/0/4                    | 5/0/4                    |
| 2 to 8 KB   | 11    | 6/1/4                    | 7/0/4                    |
| 8 to 16 KB  | 3     | 2/1/0                    | 3/0/0                    |
| 16 to 32 KB | 2     | 0/0/2                    | 2/0/0                    |

`main...HEAD`, the three v1.3 branches merged so far (this branch's own work is uncommitted, so the range cannot see it): 20 files a review would read.

| num_ctx | whole | window | none              |
| ------- | ----- | ------ | ----------------- |
| 16384   | 12    | 2      | 6 (6 added files) |
| 32768   | 14    | 0      | 6 (6 added files) |

| Patch size  | Files | whole/window/none at 16k | whole/window/none at 32k |
| ----------- | ----- | ------------------------ | ------------------------ |
| under 2 KB  | 6     | 6/0/0                    | 6/0/0                    |
| 2 to 8 KB   | 8     | 5/1/2                    | 6/0/2                    |
| 8 to 16 KB  | 3     | 1/1/1                    | 2/0/1                    |
| 16 to 32 KB | 3     | 0/0/3                    | 0/0/3                    |

`--range main`, which reads the working tree and so does cover this branch, gives whole 14, window 4, none 7 at 16k and whole 19, window 0, none 6 at 32k over 25 files. Raw output for all three: `~/ReviewBot-runs/2026-09-12/filectx/budget-*.txt`.

Two readings the tables make plain. Every `none` in them is a file the range added, whose diff is already the whole file, or a patch of 16 KB and up that has filled the budget on its own: the size gate reads the patch alone, so turning the switch on cannot change which files are skipped, and what it does instead is leave the largest diffs with no context at all, silently. And 32768 buys three or four mode changes on this codebase and otherwise buys seconds, which is why the second machine round is a second `FILE_CONTEXT_LINES`, not a second context size.

The padded case file for tier two was emitted as a smoke check and not run:

```
.venv/bin/python scripts/file_context_budget.py --emit-corpus-cases \
  ~/ReviewBot-runs/2026-09-12/filectx/corpus-padded.json --pad --redteam
```

94 cases (76 planted and clean, 15 red team, 3 new file-borne), 93 of them carrying a synthesised file. `practice_lockfile_deleted` carries none, because it is the corpus's only javascript case and there is no clean javascript case to pad it from; padding is drawn only from clean cases of the same language, so it cannot plant a second bug. Each is padded with whole clean-case bodies, one after another with a blank line between them and a suffix on the names when a body is used twice, rather than fragments of several cases interleaved, which was broken code shown to one variant of the round and not the other. Example: `sqli` has a 265-byte patch and a 3,659-byte, 150-line file, with the hunk's own lines sitting at the numbers its header implies. The padding is still synthesised code and not real code, and the hunk is written over whatever padding sits at its numbers, so the file reads as the file the hunk came from rather than compiling; a finding filed on the padding is a false positive by construction, and only the `+filectx` variant of a round is shown the padding at all. That asymmetry is the point of the round rather than a flaw in it, and the tier two section has to say so again when it is written.

## Tier two, one model-hour, no judges: not yet run

The decision gate for the switch. Read recall, false positives per clean diff, obedience on the three file-borne red-team cases, `dropped_outside_diff` beside `dropped_unlocatable`, and the seconds and prompt tokens per case. A losing result here stops the branch before anyone spends an afternoon judging.

```
cd backend
# 94 cases at roughly 13 s off and 25 to 35 s on: about an hour
.venv/bin/python -u scripts/prompt_eval.py \
  --cases-from-file ~/ReviewBot-runs/2026-09-12/filectx/corpus-padded.json \
  --variants new,new+filectx --repeats 1 --model qwen3.5:9b \
  --out ~/ReviewBot-runs/<date>/prompt-runs --tag padded16k --unload
.venv/bin/python scripts/prompt_judge.py ~/ReviewBot-runs/<date>/prompt-runs padded16k \
  --corpus="$HOME/ReviewBot-runs/2026-09-12/filectx/corpus-padded.json" --failures \
  > ../docs/benchmarks/runs/<date>/padded16k.leaderboard.md
# the window is the knob that ships, so the second run is a wider one, not a wider context
.venv/bin/python -u scripts/prompt_eval.py \
  --cases-from-file ~/ReviewBot-runs/2026-09-12/filectx/corpus-padded.json \
  --variants new+filectx --file-context-lines 120 --repeats 1 --model qwen3.5:9b \
  --out ~/ReviewBot-runs/<date>/prompt-runs --tag padded16k-w120 --unload
# and the overhead constant, re-derived from a run whose cases carry no file text
.venv/bin/python scripts/file_context_budget.py --emit-corpus-cases ~/ReviewBot-runs/<date>/filectx/corpus.json
.venv/bin/python -u scripts/prompt_eval.py --cases-from-file ~/ReviewBot-runs/<date>/filectx/corpus.json \
  --variants new+filectx --repeats 1 --model qwen3.5:9b --out ~/ReviewBot-runs/<date>/prompt-runs --tag overhead --unload
.venv/bin/python scripts/prompt_overhead.py ~/ReviewBot-runs/<date>/prompt-runs/overhead-new_filectx.json \
  ~/ReviewBot-runs/<date>/filectx/corpus.json
```

**Not yet run.** `PROMPT_OVERHEAD_TOKENS` stays at 1400 against a largest measured overhead of 1206 until that last command says otherwise; whatever it becomes changes no skip decision at the defaults, because `MAX_PATCH_BYTES` of 32,000 is already under the gate's 36,355 bytes at 16384.

## Tier three, the machine and two judges: not yet run

Precision on real pull requests, reviewer only, because the cross-examiner is still handed the patch alone on this branch. The control is a switch-off run over the same fixed set judged the same way, not the 22 findings and 0 useful of 2026-09-07, which was the 9B with the 12B cross-examining.

```
cd backend
.venv/bin/python scripts/precision.py run --out ~/ReviewBot-runs/<date>/precision-runs --tag ctx-off \
  --model qwen3.5:9b --no-cross --unload
.venv/bin/python scripts/precision.py run --out ~/ReviewBot-runs/<date>/precision-runs --tag ctx-on \
  --model qwen3.5:9b --no-cross --unload --file-context
.venv/bin/python scripts/precision.py sheet ~/ReviewBot-runs/<date>/precision-runs ctx-on --out ~/ReviewBot-runs/<date>
# two independent judges fill the skeleton, then
.venv/bin/python scripts/precision.py merge <filled-a>.json <filled-b>.json
.venv/bin/python scripts/precision.py score ~/ReviewBot-runs/<date>/precision-runs ctx-on --markdown
```

**Not yet run.** About an hour and a half of machine for the two tags over the eleven pull requests, then an afternoon of judging. The judged table belongs in `../REVIEW_QUALITY.md` and the rolling row in `PRECISION.md`, because every number in this directory comes from `prompt_eval` ranked by `prompt_judge` and measures recall on planted diffs.

Before any of it against live pull requests: the App installation has to accept **Contents: read**. Until it does, the wider token mint comes back 422, the provider narrows to the two permissions a review needs and retries, and every review runs on the patch alone, which is the same thing as the switch being off: the prompt narrows with the token, so a review on a narrowed installation is sent the incumbent system text and the incumbent human message, not the file-context rule with an empty block under it.
