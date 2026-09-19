# What ReviewBot said about its own v1.3 pull requests, and what to change

Written 2026-09-19, the day the v1.3 branches and the waiting dependency bumps (PRs 41 to 51) were merged to `main` so the bot could be used for other work. Nothing here is fixed yet. It is the brief for the next session.

ReviewBot reviewed PRs 39 to 45 on 2026-09-12 with the live App: `qwen3.5:9b` reviewing, `gemma4:12b` cross-examining, `VERIFY_FINDINGS` off, `FILE_CONTEXT` off. Every inline comment was checked against the code at the commit it was made on, by reading the line, running the code where a claim could be run, and `ruff` for the import claims. The line numbers below are `main`'s at 2876cf2, which match the reviewed heads for every file quoted.

## 1. The short version

- **77 inline comments on 63 lines, and none of them is a defect worth fixing.** Severities: 5 critical, 21 high, 10 medium, 41 low. PR 39 was docs only and drew none.
- **One suggestion would have broken something.** `file_context.py:148` was told to decode with `validate=True`. GitHub's contents API wraps base64 every 60 characters, and `validate=True` rejects the newline (checked: `binascii.Error: Only base64 data is allowed`). Every real file would decode as None, so file context would switch itself off with no error, and no test would notice (section 2).
- **What it missed is what a linter finds.** ReviewBot claimed ten unused imports and was wrong ten times. `ruff --select F401` finds seven real ones on the same files, and the bot flagged none of them.
- **The cross-examiner did the most useful work.** The reviewer raised 210 findings across PRs 40 to 45, and `gemma4:12b` removed 135 of them (64%) as false positives. The 77 above are what survived it.
- **The stack re-reviewed itself.** Each stacked pull request was opened against `main`, so 74% of the findings on PRs 42 to 45 were on lines a lower pull request had added (section 4).
- **Most of the noise has a mechanical cause, not a model one.** Section 5 has one line per cause. The largest is test fixtures holding canned model replies ("Parse it.", "Put it back."), which the reviewer copied back out as findings, critical severity included.

## 2. Fix the code (small, and none of it raised by the bot)

1. **Pin GitHub's wrapped base64 in a test.** `tests/test_file_context.py:108-111`, and the fixtures at `tests/test_runner.py:418` and `tests/test_github_client.py:228`, only use `b64encode`, which never wraps. Add a case like `file_context.decode(base64.encodebytes(b"print('hi')\n" * 20).decode()) == "print('hi')\n" * 20`, and make the `test_github_client.py` fixture's `content` wrapped. Then a `validate=True` change fails the suite instead of passing it.
2. **Remove seven unused imports** (`ruff check --select F401 backend`):
   - `tests/test_review_generation.py:13` `review_prompt` (added by PR 44; keep `review_prompt_with_context`)
   - `scripts/review_diff.py:33` `Awaitable`, `Callable` (added by PR 40)
   - `database/repositories/webhook_repository.py:4` `Any`, `Dict`
   - `scripts/prompt_eval.py:42` `time`
   - `tests/test_lifespan.py:7` `httpx`
3. **Put `ruff check --select F401` in the backend CI job** beside `pytest`. It is exact where the model guesses, and it makes an "unused import" finding from the model redundant (section 3, item 8).
4. Optional nits: `tests/test_git_diff.py:3` says "Every fixture below was produced by git 2.50", but the combined-diff fixture at :356-358 is hand-built, so say "Every module-level fixture" or mark :356. `services/llm.py:70-73` repeats the same two-form tag test twice and could be one helper. `tests/test_runner.py:414` imports `base64` inside a function.
5. **Commit Next 16's own `tsconfig.json` and `next-env.d.ts`.** Every `npm run build` rewrites both: `jsx` becomes `react-jsx`, `.next/dev/types/**/*.ts` joins `include`, and the routes reference becomes an import. So the working tree shows them modified after any build. Build once, run prettier on `tsconfig.json`, check CI stays green, and commit the result.

## 3. Fix the bot, ranked by comments removed per hour

Every item says how it ships. The rule has not changed: a post-filter ships on a replay of the recorded runs before and after, and a prompt change ships on a corpus measurement with the machine free, or not at all. Each new drop rule also needs:

- its name added to `DROP_RULES` (`scripts/precision.py:104`) and to `prompt_eval.py`'s drops dict (:263-271), which `tests/test_precision.py:572` keeps equal;
- the filename passed in both classify calls (`precision.py:442`, `prompt_eval.py:272`), or their counters miss drops the live path makes.

The dry-run counts below apply a rule to the 77 posted comments and to the 22 round-0 precision findings, with no model involved. They are not a replay.

1. **Drop a finding the patch already contains as data** (post-filter, measure by replay). Removes 14 comments, including all five criticals.
   - Six test files hold 28 lines of canned replies: `test_prompt_eval_replay.py` has 12, `test_review_generation.py` 5, `test_cross_examine.py` 4, `test_review_diff.py` 4, `test_sequential_phases.py` 2, `test_verify_pass.py` 1.
   - Each reply carries its own evidence inside the same patch, so the locator finds the quote (`services/diff.py:155-160`). `_norm` (:68-71) even turns `"` into `'`.
   - The copied confidences (0.9, 0.95) clear the floor, and no drop rule looks at them.
   - Fix: in `postprocess`, just after `drop_rule` (`services/ai_reviewer.py:386-389`), drop as `echoed` a finding whose `'title': '<title>'` or `'recommendation': '<rec>'` appears in the added lines, both put through `diff._norm`. Put the helper beside `quotes_text` (`diff.py:204-217`).
   - Cross-examiner additions pass through `postprocess` (:522), so they are covered too.
   - Dry run: fires on none of the 106 corpus cases and none of the precision findings.
2. **Drop "delete this comment" when the comment explains** (post-filter in `drop_rule`, measure by replay). Removes 13 comments.
   - 13 of the 77 ask to delete or shorten a comment or docstring that records a reason the code cannot show. Nine of them are on `prompt_eval.py` in PR 45. PR 44 posted none on the byte-identical patch, so this is sampling, not the code.
   - The precision ledger has three more, all judged not real. `style_preference` is 15 of round 0's 44 votes.
   - The simplicity rule at `prompts.py:47` and :155 ("the shorter form that does the same job") never mentions comments, and the model reads "delete" as permission.
   - Add `comment_prose` beside `_praise` (`ai_reviewer.py:126-150`), which has the same shape: a text rule with guards.
   - It fires on quality findings only, when either:
     - the evidence opens a comment or docstring, or
     - the title or recommendation asks to remove, shorten, simplify or trim a comment, docstring or documentation, or calls one redundant, verbose, obvious or explanatory.
   - It keeps the finding when the text says the comment is stale, outdated, wrong, misleading, or contradicts the code, because a comment that lies is a real finding.
   - It leaves security findings alone. LLM01 depends on them, and `prompts.py:110` says a comment being a comment is never a reason to refute.
   - Join the title and recommendation with `. ` before matching. Without the full stop, "delete duplicate logic" reached "docstring" in the next sentence.
   - The regexes were dry-run tested by the triage:
     ```python
     _COMMENT_START = re.compile(r'^\s*\+?\s*(#|//|/\*|\*|<!--|"""|\'\'\')')
     _PROSE_ASK = re.compile(r"\b(remove|delete|drop|shorten|simplify|trim|cut|condense)\b[^.]{0,60}\b(comments?|docstring|documentation|prose|explanation)\b"
                             r"|\b(redundant|verbose|unnecessary|obvious|explanatory)\s+(inline\s+)?(comment|docstring|documentation|prose)", re.I)
     _STALE = re.compile(r"\b(stale|outdated|out of date|no longer|wrong|incorrect|inaccurate|misleading|contradict\w*|mismatch\w*|false)\b", re.I)
     ```
   - Dry run: drops exactly the 13. Its guard keeps `prompt_judge.py:223`, whose text says the comment "contradicts the logic". It drops 3 of the precision findings, all not real.
3. **Let a repository declare its fixture files** (config). Removes 11 comments.
   - Add a `REVIEW_SKIP_PATHS` setting: comma-separated fnmatch patterns, the idiom `services/redaction.py:149` already uses.
   - Check it in `_skip_reason` (`services/review_runner.py:109`) with the reason "declared test fixture", so the file shows under Not reviewed rather than vanishing.
   - For this repository: `backend/tests/prompt_redteam.py`, `backend/tests/prompt_corpus.py`, `backend/tests/precision/*`. Both files say in their docstrings that they hold planted bugs (`prompt_redteam.py:8-9`, `prompt_corpus.py:11-13`).
   - The cost is that helper code in those files goes unreviewed, visibly.
4. **Keep accessibility to files that can render** (post-filter, measure by replay). Removes 3 comments.
   - `prompts.py:41` says "wherever the diff renders interface", but nothing after the model enforces it.
   - The three posted ones put WCAG on Python:
     - 2.4.7 on a pytest assert, `test_retention.py:72`;
     - a fallback chain, `git_diff.py:86`;
     - 4.1.3 on a prompt label, `file_context.py:87`.
   - The cross-examiner's notes name at least nine more that it refuted, all on Python.
   - The cross-examiner cannot relabel a finding: `CrossVerdict` (`services/schemas.py:73-75`) has no category field. So `git_diff.py:86` posted as accessibility although its note called it a logic issue.
   - Fix: drop as `off_ui_accessibility` when the category is accessibility and `get_file_language(filename)` (`utils/helpers.py:22-28`) is not html, css, scss, sass, less, vue, svelte, javascript or typescript. JS and TS stay because they can build DOM.
   - All 16 corpus accessibility cases are `.tsx`, `.html` or `.css`, so recall there cannot move.
5. **Dedupe by line and category, not line and title** (post-filter, measure by replay). Removes 2 comments.
   - The key is `(located, title)` (`ai_reviewer.py:406-410`), so any rewording gets through. PR 43 posted a critical and a high on `test_review_diff.py:24` for the same string. PR 44 posted the same title twice on `prompt_corpus.py:39` and :40.
   - Key on `(line, category)` instead. Keep the more severe finding (then the more confident), and append "Also raised on this line: <title>".
   - Also fold a repeat of the same title in the same file into its first line, which enforces `prompts.py:39` ("once per problem on its first line").
   - The cross-examiner's additions already get the line-level treatment (:526-533).
6. **Drop a "remove X" finding whose evidence is a line the diff removed** (post-filter, measure by replay). Removes 2 comments.
   - PR 43 keeps a finding that quotes a removed line, so "the guard is gone" is still reported.
   - The same exception lets "remove the unused `delete` import" through, quoting `-from sqlalchemy import delete, ...`, the line that already removed it. PR 41 drew that finding before the rule existed, and a local `review_diff.py` run of the same commit on `main` on 2026-09-19 still posted it.
   - `diff.py:142` on PR 44 is the same shape.
   - Narrow the exception so it doesn't apply when the recommendation asks for the removal the diff already made.
7. **A diff held inside a string literal** (post-filter, measure by replay). The general form of item 3, for repositories that declare nothing.
   - Drop as `in_string` a finding whose located line is a single string literal that starts with a diff marker (`+`, `-` or space) and contains the evidence. Check it after `locate_evidence_kind` (:393).
   - It catches the red-team plants and `test_prompt_eval_replay.py:173-175`, and fires on no corpus plant and no precision finding.
   - It rests on a line regex, so measure it before anything depends on it.
8. **Unused-import findings with no file in view** (post-filter, measure by replay, after `ruff` is in CI).
   - With `FILE_CONTEXT` off the model sees a hunk, not the file, so it cannot know whether an import is used. It was wrong 10 times out of 10 here.
   - Drop quality findings titled as an unused import when the review had no file context.
   - Precision round 0 has the same class: 19 of its 44 wrong judgements were claims about imports, callers and identifiers the hunk could not show.
9. **Say what the cross-examiner did** (renderer, unit test).
   - "Cross-examined by `gemma4:12b`: 0 added, 60 refuted", above 21 findings, reads as 60 of the 21 being disputed.
   - What happened is that a `false_positive` verdict at 0.5 or above drops the finding (`ai_reviewer.py:514-518`). Only a less confident verdict keeps it, annotated "The cross-examiner disagreed" (:519-521). None of the 77 carry that note.
   - Across PRs 40 to 45 the reviewer raised 210 findings and the cross-examiner removed 135 of them (64%), which is the most useful thing the pipeline did.
   - Rewrite `services/comment_renderer.py:179-180` along the lines of "`gemma4:12b` removed 60 findings as false positives and added 0; the 21 below are what survived."
   - Refuted findings are not stored (`review_runner.py:236-243`), so they exist only in the logs. Storing them with a posted flag is a schema change for later.
10. **Say when coverage was partial** (code, unit tests).
    - `backend/scripts/precision.py` (76 KB) and `backend/tests/test_precision.py` (55 KB), the biggest new code in v1.3, were skipped on all four stacked reviews as over `MAX_PATCH_BYTES`. The headline still read as a full review.
    - First, put a code file skipped for size into the warning line (`comment_renderer.py:170-171`).
    - Second, retry an unreadable reply once with a fresh nonce, after `parse_file_review` (`ai_reviewer.py:667`), and log `output_tokens` on failure so truncation can be told from garbage.
      - `reviews.db` has 9 unreadable replies in 374 reviewed files (34 reviews).
      - `git_diff.py` failed on PR 40, and its identical patch reviewed fine on PRs 42 and 43.
    - Later, split an oversized patch. An added file is one hunk, so it has to be cut at line boundaries, preferably top-level `def` or `class`, with a correct header per piece. That needs a live round, because a replay cannot create the new calls.
11. **Review only what changed since a reviewed head** (code, respx tests, no model measurement).
    - A pull request's files are base...head (`github_client.py:113`), and heads are recorded (`review_runner.py:366-371`). But `completed_for` (`review_repository.py:42-46`) is keyed by pull request number.
    - Look for the newest commit of the pull request that already has a completed review under any number, and review `compare/{that}...{head}` instead, saying so in the body.
    - PR 45 would have been 9 files, not 36. The same path serves a push to one pull request.
    - It needs a guard that moves a finding outside the pull request's own diff into the body, since GitHub rejects a review with a comment off the diff.
12. **Run the two `FILE_CONTEXT` rounds.** `docs/benchmarks/2026-09-12-file-context.md` is a stub with the commands written and marked **not yet run**. It was the biggest single lever in the roadmap, and it ships off.
13. **Round-four prompt candidates** (prompt, measured on the corpus with the red-team injection recall held, and with `precision.py`):
    - a. `prompts.py:37`, after the LLM01 sentence: injection is text addressed to the reviewer of this change. A comment explaining this code's own settings, tests or history is not injection. A string or fixture the code only holds as data is a finding only when the code runs it or sends it to a model.
      - Six comments were the rule firing on developer prose ("so the rule is off here", "the real-code audit").
      - Round 0 agrees: all five of its injection-titled findings were judged not real, three of them on prose.
    - b. `prompts.py:145`: add "or the problem exists only inside a string, fixture or canned reply that nothing executes; name the literal" to the false-positive definition.
      - Narrow "claims an audit" at :143 to text addressed to a reviewer or a model.
      - As written, :143 tells the cross-examiner to _add_ injection findings the reviewer walked past, which is where the `test_settings.py:93` comment came from.
    - c. Give the cross-examiner and verifier the located line, not only the trimmed evidence (`ai_reviewer.py:481-483` and :573-576), so they see `"+eval(user_input)\n"` with its quote marks.
    - d. `prompts.py:41`: a file that renders no interface (Python, a CLI, a test) gets no accessibility finding. `prompts.py:47` and :155: an explanatory comment or docstring is never a simplicity finding, and one that contradicts the code is a quality finding. These are the prompt side of items 4 and 2. Run them as variants beside the post-filters, not instead of them.
    - e. Before `VERIFY_FINDINGS` is ever turned on, `prompts.py:110` needs the same narrowing as b. It tells the verifier that a finding quoting a comment or string "is real whenever that line exists in the diff", which would confirm this whole class.

## 4. Fix the process

**Stacked pull requests re-review themselves.** PRs 42 to 45 were a stack, but each was opened against `main`, so each review covered every branch below it:

| PR  | files reviewed | findings | files its own commit touched | findings on lines its own commit added | model time |
| --- | -------------: | -------: | ---------------------------: | -------------------------------------: | ---------: |
| 42  |             11 |        4 |                            4 |                                      1 |      721 s |
| 43  |             20 |        8 |                           15 |                                      3 |    1,145 s |
| 44  |             34 |       21 |                           27 |                                     15 |    2,360 s |
| 45  |             36 |       39 |                            4 |                                      0 |    2,392 s |

- 53 of the 72 findings (74%) were on lines a lower pull request had added.
- 13 repeat a finding an earlier review in the stack had already posted.
- The four reviews took 110 minutes of laptop, about half of it on files already reviewed.
- Re-reviewing also re-rolls the model: `git_diff.py` with identical bytes was unreadable on 40, drew one finding on 42 and none on 43.

Next time, open each layer against the branch below it (`gh pr create --base <branch below>`). Merge bottom up, and retarget the next pull request onto `main` before deleting a merged branch. Retargeting costs no review, because `edited` is not in `REVIEW_TRIGGERS` (`models/github.py:34`).

**Dependabot bumps `requirements.txt` and CI installs `requirements.lock`.** PR 48 bumped langchain-core in `requirements.txt` only. CI and `Dockerfile.local` both install the hash-pinned lock, so its green run tested the old version. It was relocked by hand on 2026-09-19 (937b9c6, both hashes checked against PyPI) before it merged.

- Add a check that fails when the two disagree. This one is stdlib only, runs offline, passes on `main` ("13 pins agree") and fails on dependabot's original commit c35fd08 ("langchain-core: requirements.txt 1.6.2, requirements.lock 1.6.1"). Put it in `backend/tests/test_requirements_lock.py`, which needs no workflow change, or run it as a step before Install in `ci.yml`:
  ```python
  PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==([^\s;#]+)")
  def pins(path):
      out = {}
      for line in Path(path).read_text().splitlines():
          m = PIN.match(line.strip())
          if m:
              out[re.sub(r"[-_.]+", "-", m.group(1)).lower()] = m.group(2)
      return out
  want, locked = pins("requirements.txt"), pins("requirements.lock")
  bad = [f"{n}: requirements.txt {v}, requirements.lock {locked.get(n, 'missing')}"
         for n, v in sorted(want.items()) if locked.get(n) != v]
  ```
- Relocking: `pip-compile --generate-hashes --no-emit-index-url --output-file=requirements.lock --strip-extras --upgrade-package <name>==<version> requirements.txt` from a scratch venv, then restore the lock's header line. The header's `--no-index` means "no package index" to current pip-tools and fails to resolve anything.
- For the longer term, dependabot's pip-compile support expects a `.in` file compiled into a `.txt`. Renaming `requirements.txt` to `requirements.in` and `requirements.lock` to `requirements.txt` would let it relock with hashes itself. It touches `ci.yml:26,30`, `Dockerfile.local:10-11`, `README.md:74`, `backend/README.md:26`, `docs/HOSTED_MODEL_PLAN.md:85` and `docs/TEST_PLAN.md:57`. Confirm with one dependabot run after the rename, and keep the check.
- **React and react-dom must move together.** PR 49 (react 19.3.0) failed CI alone because React refuses to run with mismatched versions. PR 51 (react-dom) pulled react up with it, and dependabot then closed 49 as no longer needed. A `groups:` entry in `.github/dependabot.yml` for `react`, `react-dom`, `@types/react` and `@types/react-dom` makes that one pull request.

**Measuring the fixes.** Precision round 0 is marked `"replayable": false` because it was rebuilt from `reviews.db`, and `precision.py replay` refuses it (:1161-1167). Record round 1 with `precision.py run` and judge it once (commands in `docs/benchmarks/PRECISION.md`). After that, every post-filter above is a replay with no model loaded, and it passes if every finding that vanishes was judged not real. `prompt_eval.py --replay` works on the existing pass files today.

## 5. Why each comment was wrong, by cause

| Cause                                                                               | Comments |  Lines | What would have stopped it                                                           |
| ----------------------------------------------------------------------------------- | -------: | -----: | ------------------------------------------------------------------------------------ |
| Canned model replies in test fixtures, copied back as findings                      |       15 |      7 | Section 3, items 1 and 5                                                             |
| Planted red-team bugs, working as designed                                          |        9 |      6 | Item 3 or 7                                                                          |
| Injection rule firing on developer prose or fixture data                            |        6 |      5 | Item 13a, 13b                                                                        |
| "Delete this comment or docstring" where it records a reason                        |       13 |     13 | Item 2                                                                               |
| Security claims the code already answers                                            |        4 |      4 | None cheap; ordinary model error                                                     |
| Security shapes that are deliberate (throwaway keys, fake tokens, the file listing) |        7 |      6 | Item 13a                                                                             |
| Unused-import claims (not counting the three echoes)                                |        6 |      6 | Item 8                                                                               |
| Accessibility on backend Python                                                     |        3 |      3 | Item 4                                                                               |
| Quoting a line the diff removed (beyond the import)                                 |        1 |      1 | Item 6                                                                               |
| Other quality misreadings                                                           |       13 |     13 | None; ordinary model error                                                           |
| **Total**                                                                           |   **77** | **63** | `test_sequential_phases.py:41` drew comments of two causes, so the column sums to 64 |

## 6. Every comment, line by line

Paths are under `backend/`. PRs list every review that posted the comment. "By design" means the thing flagged is deliberate and documented; "false positive" means the claim is untrue of the code.

| Line                                            | PRs                | Bot said                                                       | Verdict                                | Why                                                                                                                                                                                  |
| ----------------------------------------------- | ------------------ | -------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `tests/test_prompt_eval_replay.py:173`          | 45                 | medium: unused import, "Delete it."                            | false positive                         | `" import os\n"` is a line of the `CTX_DIFF` string; title, severity and recommendation copied from `CTX_REPLY` :180-181                                                             |
| `tests/test_prompt_eval_replay.py:174`          | 44, 45             | high: the authorisation check is gone, "Put it back."          | false positive                         | the `"-assert_authorised(user)\n"` string; copied from `CTX_REPLY` :182-183                                                                                                          |
| `tests/test_prompt_eval_replay.py:175`          | 44, 45             | critical: eval on user input, "Parse it."                      | false positive                         | the `"+eval(user_input)\n"` string; copied from `CTX_REPLY` :178-179                                                                                                                 |
| `tests/test_prompt_eval_replay.py:341`          | 44, 45             | high, then medium: unchecked config read, "Guard it."          | false positive                         | last line of a `file_text` string; the fixture reply at :343-344 says the same, as quality                                                                                           |
| `tests/test_prompt_eval_replay.py:346`          | 45                 | high: invented command execution, "Delete it."                 | false positive                         | the fixture's own deliberately invented finding, placed on the line holding its evidence key                                                                                         |
| `tests/test_review_diff.py:24`                  | 43 (twice), 44, 45 | critical: eval on user input; high: LLM01 injection            | false positive                         | `REPLY = json.dumps({"findings": [`, a canned reply; PR 43 posted two findings on it                                                                                                 |
| `tests/test_review_diff.py:8`                   | 43, 44, 45         | low: unused import `os`                                        | false positive                         | used at :91, `dict(os.environ, ...)`; the title matches `TWO_FINDINGS` at :30-31                                                                                                     |
| `tests/prompt_redteam.py:274`                   | 44, 45             | high: SSRF                                                     | by design                              | planted bug of case `file_audit_note_ssrf`; plants "live inside diff strings and are never executed" (:8-9)                                                                          |
| `tests/prompt_redteam.py:294`                   | 45                 | high: injection via forged file context                        | by design                              | the forged audit note of that case's `file_text`                                                                                                                                     |
| `tests/prompt_redteam.py:322`                   | 44, 45             | medium, then high: XSS                                         | by design                              | planted in `file_forged_context_marker_xss`                                                                                                                                          |
| `tests/prompt_redteam.py:340`                   | 45                 | high: forged context markers                                   | by design                              | the forged span label that case tests                                                                                                                                                |
| `tests/prompt_redteam.py:367`                   | 44, 45             | high: unsafe YAML                                              | by design                              | planted in `file_sentence_and_link_yaml`                                                                                                                                             |
| `tests/prompt_redteam.py:385`                   | 45                 | high: forged review markers, link exfiltration                 | by design                              | the planted request; the review bodies contain neither the sentence nor the link, so it was not obeyed                                                                               |
| `tests/prompt_corpus.py:39`                     | 44                 | medium: hostile text in model context                          | false positive                         | `file_text: str = ""`, a dataclass field with an empty default                                                                                                                       |
| `tests/prompt_corpus.py:40`                     | 44                 | medium: same                                                   | false positive                         | `file_injection: bool = False`, a flag                                                                                                                                               |
| `tests/test_prompt_eval_replay.py:228`          | 42                 | medium: LLM01 in a test fixture                                | false positive                         | a throwaway candidate prompt; `prompt_eval.py:110-111` requires exactly one `{data_begin}` and one `{data_end}`                                                                      |
| `tests/test_sequential_phases.py:41`            | 43, 44             | high: injection (43); low: jargon comment (44)                 | false positive                         | the comment records why :43 sets `CONTEXT_LINE_FINDINGS`                                                                                                                             |
| `tests/test_sequential_phases.py:43`            | 45                 | low: unnecessary override                                      | false positive                         | needed: under the shipped `drop`, CONFIRM's addition on a context line is dropped and the asserts at :61 and :63 fail                                                                |
| `tests/test_settings.py:93`                     | 43, 45             | low: injection, added by the cross-examiner                    | false positive                         | docstring prose on why the test pins `drop`                                                                                                                                          |
| `tests/test_retention.py:72`                    | 41                 | medium accessibility: assert lacks a message, WCAG 2.4.7       | false positive                         | a pytest assert; pytest reports the failing clause                                                                                                                                   |
| `services/git_diff.py:86`                       | 42                 | low accessibility: no handling for malformed sections          | false positive                         | a documented fallback chain (:56-59); a section with no hunk is reported skipped, pinned at `test_git_diff.py:261-272`                                                               |
| `services/file_context.py:87`                   | 45                 | medium accessibility: labels lack semantic context, WCAG 4.1.3 | false positive                         | the span label inside the prompt the model reads; no UI renders it                                                                                                                   |
| `tests/test_review_generation.py:4`             | 44                 | low: unused `re`                                               | false positive                         | used at :617. `ruff` flags `review_prompt` at :13 instead                                                                                                                            |
| `tests/test_file_context.py:4`                  | 45                 | low: unused `base64`                                           | false positive                         | used at :108-111; the comment's own body ends "No finding here"                                                                                                                      |
| `tests/test_file_context.py:5`                  | 45                 | low: unused `re`                                               | false positive                         | used at :76                                                                                                                                                                          |
| `services/github_client.py:4`                   | 45                 | low: unused `re`, `time`                                       | false positive                         | `re` at :17, `time` at :95                                                                                                                                                           |
| `database/repositories/webhook_repository.py:6` | 41                 | low: unused `delete`                                           | false positive                         | quotes the removed line; the commit had already dropped `delete`                                                                                                                     |
| `scripts/prompt_eval.py:75`                     | 43                 | low: redundant import                                          | false positive                         | the comment concludes "no change needed"; used at :462                                                                                                                               |
| `services/diff.py:142`                          | 44                 | low: delete `_locate_single`                                   | false positive                         | already renamed to `_locate_single_kind` in PR 43; quotes a removed line                                                                                                             |
| `scripts/review_diff.py:213`                    | 45                 | high: injection via range spec                                 | false positive                         | argv list, no `shell=True` anywhere in production code, leading dashes refused at :93-95, `--` appended at :105, repo resolved absolute at :207, pinned at `test_review_diff.py:219` |
| `scripts/file_context_budget.py:75`             | 44                 | medium: no leading-dash validation                             | false positive                         | :75-77 _is_ that validation                                                                                                                                                          |
| `tests/test_github_client.py:275`               | 44                 | medium: traversal check not in production                      | false positive                         | `services/github_client.py:148-151` refuses empty, absolute, `.` and `..` segments                                                                                                   |
| `services/file_context.py:148`                  | 45                 | high: unsafe base64, use `validate=True`                       | false positive, and the fix is harmful | size cap, NUL check and strict UTF-8 follow at :151-154; `validate=True` rejects GitHub's wrapped payload                                                                            |
| `scripts/file_context_budget.py:48`             | 44                 | high: secret in the environment                                | by design                              | an in-memory RSA key that authorises nothing, needed because Settings parses the key at import (`config/settings.py:255-261`)                                                        |
| `scripts/file_context_budget.py:50`             | 44                 | high: generated key as env value                               | by design                              | same; set with `os.environ.setdefault`, never written or printed                                                                                                                     |
| `tests/test_runner.py:406`                      | 44, 45             | high: secrets in test constants                                | by design                              | a fake token built by concatenation so no literal sits in the source; it drives the redactor                                                                                         |
| `tests/test_runner.py:529`                      | 44                 | low: assertion leaks secret fragments                          | by design                              | the assertion is the test: the model never saw the token                                                                                                                             |
| `tests/test_runner.py:546`                      | 44                 | low: secret-like mock                                          | false positive                         | quotes `[REDACTED:assigned-secret]`, which is not in the file; the real value is the mock `ghs_narrow`                                                                               |
| `services/ai_reviewer.py:644`                   | 44                 | high: LLM01, file text into the prompt                         | by design, mitigated                   | off by default; redacted, defanged, nonce-labelled, boundary-counted (:617-623, :652); a finding quoting only the listing is dropped (:671)                                          |
| `scripts/review_diff.py:112`                    | 42                 | low: redundant `FileNotFoundError` handler                     | false positive                         | it turns a missing git into `CannotRun`, exit 2, the documented contract (:83-84)                                                                                                    |
| `services/ai_reviewer.py:340`                   | 42                 | low: duplicate logic                                           | false positive                         | the docstring describes the rejected alternative; no copy exists                                                                                                                     |
| `services/ai_reviewer.py:333`                   | 45                 | low: redundant function                                        | false positive                         | one definition, one caller (:402)                                                                                                                                                    |
| `services/llm.py:70`                            | 43                 | low: redundant `:latest` check                                 | false positive                         | Ollama lists `name:tag`, so a bare configured name only matches through `:latest`                                                                                                    |
| `scripts/prompt_judge.py:223`                   | 43                 | low: context-line group redundant                              | false positive                         | the comment gives the group's reason: nothing else prints those rows                                                                                                                 |
| `services/prompts.py:69`                        | 45                 | low: two prompt constants                                      | by design                              | both built from shared halves; the measured prompt is pinned byte for byte (`test_review_generation.py:549-553`)                                                                     |
| `services/review_runner.py:456`                 | 45                 | low: redundant logging                                         | false positive                         | already one structured entry, one counter per mode                                                                                                                                   |
| `tests/test_git_diff.py:267`                    | 45                 | low: unused variable                                           | false positive                         | `no_text` is used three times                                                                                                                                                        |
| `tests/test_git_diff.py:362`                    | 45                 | low: redundant assertion                                       | false positive                         | checks `files[1]`; :361 checks `files[0]`                                                                                                                                            |
| `tests/test_cross_examine.py:46`                | 45                 | low: unused `KEEP_CONTEXT`                                     | false positive                         | used at :109, :187, :267, :298                                                                                                                                                       |
| `tests/test_runner.py:413`                      | 45                 | low: consolidate routes                                        | false positive                         | `_contents_route` already is the one factory, used six times                                                                                                                         |
| `services/retention.py:36`                      | 41                 | low: new key adds load                                         | false positive                         | a rename of `deliveries`, accurate now that rows are kept                                                                                                                            |
| `tests/test_git_diff.py:3`                      | 40                 | low: delete the provenance comment                             | false positive                         | it stops someone tidying real git bytes (see the nit in section 2)                                                                                                                   |
| `tests/test_cross_examine.py:43`                | 45                 | low: delete the comment block                                  | false positive                         | it says why exactly four tests use `KEEP_CONTEXT`                                                                                                                                    |
| `database/models.py:119`                        | 41                 | low: delete inline documentation                               | false positive                         | the only model-level note on `expired`; replaced a stale list missing `interrupted`                                                                                                  |
| `scripts/prompt_eval.py:233`                    | 45                 | low: redundant docstring                                       | false positive                         | says why the cross tag goes through the constructor: so the local-only guard judges it                                                                                               |
| `scripts/prompt_eval.py:254`                    | 45                 | low: verbose docstring                                         | false positive                         | records why the count comes from `postprocess` itself: the old copy of its loop drifted                                                                                              |
| `scripts/prompt_eval.py:340`                    | 45                 | low: over-explained comment                                    | false positive                         | defines when a file-body case is an injection row, which the code cannot say                                                                                                         |
| `scripts/prompt_eval.py:367`                    | 45                 | low: remove the comment                                        | false positive                         | why `outside_diff` stays in the drop rate: leaving it out would move every comparison                                                                                                |
| `scripts/prompt_eval.py:384`                    | 45                 | low: simplify the comment                                      | false positive                         | what the fourth mode means and why it is counted                                                                                                                                     |
| `scripts/prompt_eval.py:392`                    | 45                 | low: remove the comment                                        | false positive                         | why the reported share has a different denominator                                                                                                                                   |
| `scripts/prompt_eval.py:457`                    | 45                 | low: simplify the comment                                      | false positive                         | why a replayed cross tag skips the local-only guard                                                                                                                                  |
| `scripts/prompt_eval.py:531`                    | 45                 | low: simplify the comment                                      | false positive                         | why a fully replayed run may start with Ollama down                                                                                                                                  |
| `scripts/prompt_eval.py:611`                    | 45                 | low: remove the comment                                        | false positive                         | why the policy is recorded beside the rows: so a leaderboard cannot be mislabelled                                                                                                   |

## 7. How this was checked, and what to do differently next time

Three Opus agents did the checking, read-only, against the reviewed commits. Two took the comments between them. The third read the review bodies and `reviews.db` for the patterns in sections 3 and 4. Their claims were spot-checked by hand before anything went in this file: the fixture replies at `test_prompt_eval_replay.py:172-184` and `test_review_diff.py:24-31`, the dedupe key, `.env`, the three prompt lines, `validate=True` against a wrapped payload, and `ruff` on `main`. The nine `prompt_eval.py` comments and `file_context.py:87` were read by hand.

- `gh api .../pulls/<n>/comments` returns 30 per page. PR 45 has 39, so use `--paginate`, or nine comments go missing without any error.
