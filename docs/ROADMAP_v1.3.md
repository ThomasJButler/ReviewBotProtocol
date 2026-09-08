# v1.3: make the findings worth reading

Written 2026-09-08, the day v1.2.0 shipped. v1.2 made the bot robust enough for a stranger to run. This one is about the thing that decides whether anyone keeps reading it: on the eleven v1.2 pull requests it filed 22 findings and none were worth acting on, while a Claude review of the same diffs found nine real defects and a security scan found two more. The measurement and the reasoning behind this order are in `docs/REVIEW_QUALITY.md`; this file is the work.

Every branch below already exists off `main`. They are deliberately **not** stacked: v1.2 was a stack of eleven and merging it went sideways, because deleting a base branch closes the pull request stacked on it rather than retargeting it. Independent branches merge in any order.

## 0. If the time is short: the order

1. **Two tools first (an evening each).** The offline review command and the precision measurement. Neither improves a review by itself; both make every later change fast to try and possible to judge. Without them you are back to pushing a branch and waiting an hour to learn anything.
2. **The two cheap noise cuts (an evening, then a weekend).** The added-line rule, then whole-file context. Between them they address 26 of the 44 judgements that said a finding was wrong.
3. **The corpus, then round four.** Everything after that is only as good as the diffs it is scored against, and the corpus still contains none of the shapes this codebase is made of.

## 1. The tools

**`v1.3-offline-review`: review a diff with no network.** A command that takes a `git diff`, a branch range or a file, runs the pipeline and prints the findings. `FileReviewer` never needed GitHub (it takes a filename, a language and a patch), and `backend/scripts/prompt_eval.py` already drives the whole thing over local files, so most of this exists. Reuse `services/diff.py` for the patch parsing and `services/comment_renderer.py` for the output. Worth doing first because it cuts the loop for every other item here from a push plus an hour of the machine to minutes, and because it is the only way to demonstrate the privacy claim rather than argue it. _An evening. Harness._

**`v1.3-precision`: score real pull requests, not just planted ones.** The harness only measures recall, on diffs where the answer is known. Repeat what was done by hand on 2026-09-07: take a fixed set of real pull requests, judge every finding independently against the code, record one number per round. Until it exists, a prompt that raises recall can quietly cost precision and the leaderboard shows only the gain. Store the judged set beside the corpus so the number is re-runnable, not a one-off. _An afternoon to build, an hour a round. Harness._

## 2. The noise cuts, each measured by replay before it ships

**`v1.3-added-lines`: a context line is weaker evidence than an added line.** Seven of the 44 wrong judgements were findings about lines the pull request never touched. `services/diff.py` already separates `added_lines` from `new_lines`, so the pipeline can drop such a finding, lower its severity, or require more confidence. Measure all three by replay and pick on the number, the way the praise and tag rules were picked. _An evening. Harness, entirely: no model size fixes this._

**`v1.3-file-context`: show the model the file, not only the hunk.** Nineteen of the 44 were assertions about imports, callers and identifiers that are not visible in a diff hunk, which is the single biggest cause of noise and the single biggest lever here. Send the whole file when it fits the remaining context, else a window around each hunk, and mark which part is the change. Watch `MAX_PATCH_BYTES` against `OLLAMA_NUM_CTX`: more context per file means fewer files fit, so measure the cost in seconds and in skipped files alongside the quality. _A weekend. Harness first, model second: a cloud model behind the same blindfold guesses too._

## 3. The corpus

**`v1.3-corpus-defences`: the shapes this codebase is actually made of.** All five defence-read-as-attack findings landed on a redaction pattern, a test fixture holding a hostile string, or a docstring quoting an attack. A security tool is mostly that, and the corpus contains none of it, so no prompt has ever been scored against the shape. Add a dozen clean diffs of it. Only then is a rule that downgrades a security finding whose evidence is a comment or a fixture worth writing, because only then can it be judged. _A day. Corpus, then harness._

Carried unchanged from `docs/ROADMAP_v1.2.md` section 4, and still worth doing after the above: a held-out planted set the prompts are never tuned against; a check that a finding's title names something the diff contains; the obedience check reading each case's `expected_safe_behaviour` rather than only an empty reply; a per-row silencing count beside the per-case one; a pooled judge over two tags; `--replay-verify` to match `--replay-cross`.

## 4. The security decision

**`v1.3-replay-tombstone`: keep the replay evidence longer than the review data.** From `CLAUDE-SECURITY-20260908-004806`, finding F1. GitHub's webhook signature never expires, so the only thing stopping a captured delivery being replayed is the stored body hash, and the retention sweep deletes it after a year. Keep a minimal record of delivery id, body hash and received time independently of `REVIEW_RETENTION_DAYS`, or reject a delivery whose payload is older than a freshness window. This one is a decision more than a task; the code is small either way. _An hour once decided._

## 5. Round four of the prompts

Unchanged from `docs/ROADMAP_v1.2.md` section 3, which holds the candidates written from round three's raw replies. Three of them are now ready to measure because the pipeline changed underneath them: the sentence naming `[forged-data-marker]` in the reviewer and verifier, the sentence about a recommendation that concludes there is no finding, and the tag-list sentence. Prompt text ships measured or not at all, so this needs a chain run with the machine free: about 80 minutes for a reviewer pair, about 22 for a verifier replay. `docs/benchmarks/HOW_TO_RUN_A_ROUND.md` is the procedure.

## 6. Still carried, not scheduled

From `docs/ROADMAP_v1.2.md`: re-running a review from the dashboard and comparing two reviews of the same pull request (section 2); one real fork pull request to close S6 (section 2); the server shape with both models resident (section 5); chat, voice, diagram and the learning log (section 6); the website and its generated settings reference (section 7); marking the two historical documents (section 8, done). None of them is blocked; they are simply worth less than the list above until a finding is worth reading.

## The branches, ready

| Branch                  | What                                    | Rough cost   |
| ----------------------- | --------------------------------------- | ------------ |
| `v1.3-offline-review`   | Review a diff with no network           | An evening   |
| `v1.3-precision`        | Score real pull requests each round     | An afternoon |
| `v1.3-added-lines`      | Context lines as weaker evidence        | An evening   |
| `v1.3-file-context`     | Whole file instead of one hunk          | A weekend    |
| `v1.3-corpus-defences`  | Defensive shapes as clean controls      | A day        |
| `v1.3-replay-tombstone` | Keep the replay evidence past retention | An hour      |

All six point at `main` as it stands. Check one out and start; open its pull request against `main` when it is ready. Nothing here depends on anything else here, except that the two tools in section 1 make the rest quicker to do and possible to judge.

## The rule that has not changed

Nothing ships on a guess. A pipeline change is replayed through the recorded runs before and after, and it ships on the number. A prompt change is measured on the corpus with the machine free. That rule caught two mistakes in v1.2: dropping every tag-titled finding would have cost a real catch, and the first praise rule ate nine shapes of genuine finding. Both were found by measuring rather than by reasoning.
