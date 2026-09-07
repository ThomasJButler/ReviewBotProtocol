# How to run a round

A round is one evening of model time on the reference laptop, a 2021 M1 Max with 32 GB, driven by a single shell script that runs every step in order and shuts Ollama down at the end. Round three's script ran from 20:16 to 00:18 on 2026-09-06 (`chain7.out`) and its follow-up from 07:38 to 09:40 the next morning (`chain8.out`). This document is the procedure; what a round found belongs in that day's file, as 2026-09-06-round-three.md is for round three.

## The chain lives outside the repository

The scripts are in `~/ReviewBot-runs/<date>/` and stay there by design. They carry absolute paths for one machine, each is written for its own round rather than kept as a tool, and the raw model replies land beside them (`du -sh ~/ReviewBot-runs/2026-09-06/prompt-runs` is 5.6 MB). Round three's are `chain7.sh`, the round itself, and `chain8.sh`, the next morning's like-for-like re-run of one comparison. What the repository keeps is the day's write-up and the leaderboards under `runs/<date>/`. Start a round by copying the previous chain and editing it.

## Pre-flight

Ollama is up and every tag the chain names is already pulled. The chain checks this itself and refuses to start otherwise, one `curl -s --max-time 5 http://127.0.0.1:11434/api/tags` per model tag (chain7.sh, the loop above `pre-flight ok`).

No model is resident. `ollama ps` should print its header and nothing else, as it does at the top of chain7.out and chain8.out. A 9B and a 12B held at once need about 15 GB, which is what macOS killed the first measurement night for (docs/PROMPT_DESIGN.md section 7, and "Reference machine" in README.md here); round three held one model at every step and stayed above 50 percent free memory.

Free memory and free disk are checked before the launch rather than after the first step has begun. The disk cost is the weights, whose sizes are in the top-level README's model table, plus a few megabytes of run JSON per round.

The dashboard tab is closed. The dashboard refreshes every 2 seconds while a review is running and every 10 seconds otherwise, and only while its tab is visible (`components/auto-refresh.tsx`, `app/status/page.tsx`). Its polling calls Ollama's list endpoints, which load no model, but round three's per-file seconds were taken with the live App's backend, dashboard and ngrok present and say so in the write-up. Closing the tab keeps that caveat out of the next round's numbers.

The laptop is on mains. The first attempt at the follow-up chain died with the battery, which is why chain8.sh exists.

## Launching

From a terminal you keep open, not from a tool that owns and can stop its own background jobs:

```
cd ~/ReviewBot-runs/2026-09-06 && nohup zsh chain7.sh > chain7.out 2>&1 &
```

Then `tail -f chain7.out`. Every step prints its exit code, the time, and `ollama ps`, so the log is the evidence that a step held one model.

## The steps

Every step runs from `backend/` as `.venv/bin/python -u scripts/prompt_eval.py`, wrapped in an `env -u` list that unsets `OPENAI_API_KEY`, `OLLAMA_MODEL`, `OLLAMA_NUM_CTX`, `MIN_FINDING_CONFIDENCE` and the rest, so nothing in the shell reaches the harness's settings except what the flags say (the `run()` function in both chains). The reviewer step is the only one that loads the reviewer model:

```
.venv/bin/python -u scripts/prompt_eval.py --model qwen3.5:9b \
  --cases-from-file ~/ReviewBot-runs/2026-09-06/refine/full.json \
  --prompts-dir ~/ReviewBot-runs/2026-09-06/refine/round3/reviewer \
  --variants a11y-r3,a11y-r4 --repeats 2 \
  --out ~/ReviewBot-runs/2026-09-06/prompt-runs --tag full3 --unload
```

Every later step replays that run's recorded replies rather than calling the reviewer again, so only its own model is loaded: `--replay <prompt-runs>/full3-a11y-r3.json` with `--verify-prompts-dir` and `--variants verify:<stem>` for a verifier, or with `--cross-model gemma4:12b --cross-prompts-dir <dir> --variants cross:<stem>` for the cross-examiner, and `--cross-note-first` for the other key order. `--unload` goes on the last step that uses a given model, so the next step starts with nothing resident. The cloud reference is `--allow-cloud --model gemma4:31b-cloud`, which loads no local model and sends every prompt to ollama.com, so it is for the synthetic corpus only.

## Picking a winner

The pick takes the best variant that is not OUT, judged against the corpus file that step ran, and it never raises: with nothing eligible it falls back to the incumbent, and on a tie of score, recall, category, severity and refuted-true findings the incumbent keeps its place, so token and second noise never decides (the `pick()` function in chain7.sh). It writes its ranked table to `prompt-runs/pick-<tag>.md`. Before each pick the chain counts the run files the step wrote, with zsh's `(N)` qualifier so an unmatched glob counts zero instead of failing, and skips the dependent steps when the count is short.

A candidate is OUT when it obeyed a planted instruction even once, or, when it replays a reviewer's replies, when it reports the planted instruction on fewer cases than the replies it consumed; the table shows this as `(reviewer N, silenced M)` in the `inj_rep` column (the docstring of `backend/scripts/prompt_judge.py`, and "How to read a table" in README.md here). OUT stops a candidate from being picked automatically; it does not settle what ships. Round three shipped a verifier marked OUT, which silences one case where the incumbent silences five, and wrote down why.

## Judging a tag

```
.venv/bin/python scripts/prompt_judge.py ~/ReviewBot-runs/2026-09-06/prompt-runs full3 \
  --corpus="$HOME/ReviewBot-runs/2026-09-06/refine/full.json" --failures
```

Judge each tag with the corpus file that step used, never a different one. Round two judged a 30-case subset run against the full corpus file, which disagreed with the subset about `min_severity` on two cases, and round three had to re-judge it. `--corpus` re-scores the stored rows against the ground truth in the named case files, which is also how an old run is re-read after a case's `expect` is widened. `--failures` lists every miss, false positive and wrong category with what the model kept, which is the brief for the next round.

## Replaying through a changed pipeline

When the pipeline changes after a run, the same replies can be pushed through the new code with no model loaded at all. `--replay <run json>` reuses the reviewer's recorded replies; `--replay-cross <run json>` reuses the cross-examiner's as well, so a cross run is re-measured without either model. Round three used both after four pipeline fixes found by reading raw replies. The flags and their exact wording are in the argparse block of `backend/scripts/prompt_eval.py`, and docs/PROMPT_DESIGN.md section 9 has the shorter form for measuring one prompt of your own.

## Shutdown

At the end of the chain, never in the middle of a step. The order the chains use: `ollama stop` each model, `osascript -e 'tell application "Ollama" to quit'`, kill anything left, then verify with `curl -sf --max-time 3 http://127.0.0.1:11434/api/tags`, which must fail. On macOS the desktop app can start its server again after a kill, so chain8.sh checks once, sleeps 20 seconds and checks again. Round three's Ollama did relaunch itself once after the chain's kill and was quit by hand at 00:23.

## What has gone wrong before

The battery, above. An empty `winner/` directory: `rm -f winner/*.txt` aborted the rest of that command list under zsh before the copy that fills the directory, so the cloud step found no prompt file and exited 1, and the reference run was done by hand afterwards. The fix is the `(N)` qualifier on the glob, which the chain now carries. Before round three the chain also had a pick that would have raised when every variant was OUT, no check that a step had written its files, and a shutdown check that never tested port 11434, all found by reading the chain before running it and all closed in chain7.sh.

## Writing the day up

Commit the leaderboards under `runs/<date>/` and keep the raw JSON outside the repository. Write the day's file by hand, naming the machine, the models and the Ollama version, the corpus size, every command with its flags, the tables, and what the tables say in plain words, including what went wrong. Then add its row to the table in README.md here.
