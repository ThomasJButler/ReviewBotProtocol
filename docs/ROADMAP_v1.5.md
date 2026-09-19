# v1.5: what to fix, after ReviewBot reviewed its own markdown branch

Written 2026-09-19, after the live App reviewed PR 53 (`v1.4-markdown-review`, head cb4dcd9). Nothing here is done yet. It is the list for the next session.

v1.5 has three sources, and this file adds to the first two rather than copying them:

1. `docs/REVIEWBOT_FINDINGS_v1.3.md`, sections 2 to 4: the bot fixes written after its 77 comments on its own v1.3 pull requests turned out to be all wrong. None of them is built yet.
2. The next brief at the bottom of `docs/benchmarks/2026-09-19-markdown-round-one.md`: what `REVIEW_MARKDOWN` needs before it can be switched on.
3. This file: what the review of PR 53 got wrong, what it missed in PR 53, and where the v1.3 list has to change because of it. Section 5 adds what the first live markdown reviews showed, on the private design repository, later the same evening.

The review ran with `qwen3.5:9b` reviewing, `gemma4:12b` cross-examining, and `VERIFY_FINDINGS`, `FILE_CONTEXT` and `REVIEW_MARKDOWN` all off. So the 18 markdown files were skipped, `docs/MARKDOWN_REVIEW_PLAN.md` was skipped for size, and the review covers the 20 code files only. It took 850 s. Line numbers are cb4dcd9's; paths without a directory are under `backend/`.

## 0. The short version

- **7 comments, and none of them is right.** Six are false positives. The seventh flags a planted red-team case, which is doing its job (section 6). Following two of them would have broken something:
  - removing the imports at `review_runner.py:23` fails every review with a NameError;
  - removing the planted line at `prompt_corpus.py:2558` makes the corpus fail at import.
- **The v1.3 fixes, as written, would stop 2 of the 7.** Three of the five security findings ask for a chore: two carry the prompt's own YAGNI tag ("YAGNI: Unused import increases attack surface"), and the third asks to delete an accurate comment as "untrusted". The v1.3 comment and unused-import rules fire on quality findings only, on purpose, so they miss all three. Section 2 amends those rules for the two tagged ones; the third needs prompt candidates 13a and 13b.
- **One v1.3 rule would cost real catches.** Item 2 (`comment_prose`) was dry-run over 3,334 recorded corpus replies. It fires on `practice_dead_code_left`'s planted line four times, e.g. on "Remove the `_export_csv_old` function and its comment". The v1.3 dry run only looked at posted comments. The rule needs a guard before it ships.
- **The cross-examiner confirmed all 7.** Twice its own reason refutes the finding: "The import is used in the logic below" went out as a confirmed unused import.
- **The review body is wrong in four ways** (section 3):
  - 7 of its 11 per-file summaries misdescribe their diff;
  - the truncation notice blames GitHub for the bot's own 6,000-character budget;
  - the headline doesn't say that 19 of 39 files went unreviewed;
  - a long Not reviewed list can push a secret-bearing file out of the body altogether.
- **What it missed is in PR 53 itself** (section 1). None of this was flagged:
  - the test suite goes red on a machine whose `.env` switches markdown on;
  - the output grammar and one title rule changed for code reviews, although the pull request says the Python path is byte-identical;
  - `prompt_eval.py` now scores a code-prompt candidate and the shipped prompt on different prompts for the nine markdown cases.
- **The first live markdown reviews found nothing real** (section 5). 51 comments on three docs-only pull requests, and 0 of 15 known problems hit. Every comment on the two runs judged one by one is wrong, and the reviewer's single real catch was removed by the cross-examiner. Replies cut at the 2,000-token limit are reported as unreadable, each file is reviewed as if the rest of its pull request didn't exist, a correction gets reported as the defect it fixes, and the prompt's own example leaked into a critical. `REVIEW_MARKDOWN` should go back off in `backend/.env`.

## 1. Fix PR 53 before it merges

Items 1 to 4 are small and need no model. They are what the pull request's rollout claim rests on: "the switch defaults to off and a Python file goes through byte-identical prompts and post-processing". They belong on `v1.4-markdown-review`. The rest can go there or into v1.5.

1. **Pin the switch in the test environment.**
   - `tests/conftest.py:40-52` (`_TEST_ENV`) pins `OLLAMA_MODEL`, `STRICT_LOCAL` and others, but not `REVIEW_MARKDOWN`, and the module-level `settings` reads `backend/.env`.
   - With `REVIEW_MARKDOWN=true` in `.env`, as it is now, the suite is 10 failed, 975 passed. CI has no `.env`, which is why it stays green.
   - Nine of the failures are PR 53's: `test_full_review_against_a_fake_github`, the four cut-short tests, the model-failure test, the two file-context tests, and the PR's own `test_review_markdown_opens_md_files_only_and_leaves_rst_and_txt_skipped`.
   - The tenth is older. `.env` has `MAX_PATCH_BYTES=64000`, which `test_select_files_applies_every_rule_and_keeps_the_riskiest_under_the_cap` also reads (`KeyError: 'huge.py'`).
   - Checked: with `REVIEW_MARKDOWN=false MAX_PATCH_BYTES=32000 MAX_FILES_PER_REVIEW=25`, `test_runner.py` passes 24 of 24.
   - Fix: add all three to `_TEST_ENV`. Also make `test_runner.py:395` pass `settings.model_copy(update={"REVIEW_MARKDOWN": False})`, so it follows its own file's rule at :375 ("the developer's .env must not decide a test"). The conftest pin also covers `test_settings.py:87`, which reads the live environment.
2. **Give each prompt family its own grammar.**
   - The code chain and the document chain bind the same `output_schema()` (`ai_reviewer.py:469` and :479), and both cross chains bind the same `cross_schema()` (:475 and :481).
   - On `main` the Category enum had four values. Now every code review, even with the switch off, is offered nine, so the code reviewer can file a Python finding as `plan` or `reference`. Checked: `output_schema()['$defs']['Category']['enum']` prints all nine.
   - The replay that "matches main on all 152 rows" cannot see this. It feeds recorded replies back through the pipeline and never asks a model under the new grammar.
   - Fix: give `output_schema()` and `cross_schema()` a `categories` argument that overwrites the enum. The code chains get security, performance, quality and accessibility. The document chains get security plus the five document values.
   - Pin both lists in `test_schema_shape.py`, the code list equal to `main`'s. Then switch-off sends `main`'s request, and the replay claim holds.
3. **Keep the widened title rule to documents.**
   - `_PROMPT_ECHO` (`ai_reviewer.py:53`) gained `never the name alone` for every language, and `_instruction_title` (:79) reads it with no language check.
   - The effect on code is close to nil, since the phrase is the document prompt's, but the CHANGELOG says the Python path is byte for byte unchanged. Either gate the new alternative on `DOCUMENT_LANGUAGES`, or say it in the CHANGELOG.
   - `test_review_generation.py:822` doesn't pass `language="markdown"`, so it tests the code branch. Pass it.
4. **Keep the markdown cases out of code-prompt rounds.**
   - The nine markdown cases are in `CASES`, so they run under `--all` and under an empty `--cases` (`prompt_eval.py:492-495`).
   - A `--prompts-dir` candidate is registered as the document prompt as well (:525). The incumbent `new` (:102) has no `doc_prompt`, so it gets the shipped document prompt.
   - So the recipe in `docs/PROMPT_DESIGN.md` section 9 (`--all --prompts-dir ... --variants new,<stem>`) runs a code candidate on nine rows as a code prompt reading prose, against `new` reading them with the document prompt. Round one measured that gap: 0.286 against 0.714 recall. Round four would start handicapped on 9 of 115 cases.
   - Fix, either of: leave `DOCUMENT_LANGUAGES` cases out of `--all` and the default unless they are named with `--cases` (the markdown rounds already pass `--cases $MD`) or asked for with a `--markdown` flag; or split the flag into `--prompts-dir` for code and `--doc-prompts-dir` for documents.
   - Update the corpus counts in `PROMPT_DESIGN.md` sections 7 and 9 to match.
5. **Say that documents skip the verify pass.**
   - `ai_reviewer.py:726-731` skips it for any file in `DOCUMENT_LANGUAGES`.
   - None of these say so: the `REVIEW_MARKDOWN` docstring (and therefore the generated `docs/SETTINGS.md`), `.env.example`, the CHANGELOG entry, the `VERIFY_FINDINGS` docstring ("tries to refute each finding before it is posted") and `backend/README.md:11`.
   - Fix: one sentence in each docstring, then regenerate `SETTINGS.md`.
6. **Tests that still pass when the behaviour they name breaks.** Each was checked by breaking the behaviour at runtime in a scratch copy, with the tree untouched:
   - `test_review_diff.py:254` only asserts `Language: markdown`. `HUMAN_TEMPLATE` (`prompts.py:74`) prints that for both prompts, so forcing the code prompt onto README.md still passes. Assert `"You are ReviewBot's document reviewer" in llm.seen_text`. Also pass an env file that says `REVIEW_MARKDOWN=false`, so the docstring's "lays REVIEW_MARKDOWN over the env file" is actually tested. `--no-markdown` has no test anywhere.
   - `test_runner.py:414-416` checks only that both system prompts appear somewhere in the joined calls, so swapping them between README.md and db.py still passes. Pair each call's system message with its `Language:` line.
   - Nothing tests the `FILE_CONTEXT` pairing in the runner (`review_runner.py:429`) or in review_diff (`review_diff.py:388-389`). `test_review_generation.py:739` builds the pairing itself. With `doc_review_prompt` swapped in, every markdown file fails the boundary check once `FILE_CONTEXT` and `REVIEW_MARKDOWN` are both on, and the suite stays green. Add one runner test with both switches on.
   - `test_prompt_eval_replay.py:390-432`: the candidate test runs `main()` on a Python case only and checks the `VARIANTS` dict. The code-on-docs test copies `main()`'s kwargs loop instead of calling it. Deleting `prompt_eval.py:587-588` leaves both green. Fix: run one markdown case through `main()` with a replay file, and assert on the system message the model received.
   - `test_review_generation.py:591` finds four of its five words outside the Categories line ("cross-reference", "the arithmetic on the page") and never checks `security`. Parse the one Categories line and compare it with the enum.
   - `test_settings.py:88` only uses inputs that pydantic's own bool parser handles the same way. So it passes with `REVIEW_MARKDOWN` removed from the `parse_bool` validator, although a bare `REVIEW_MARKDOWN=` line in `.env` would then stop the app at startup. Add `" yes "`, `""` and `"t"` here, and to the `VERIFY_FINDINGS` loop it was copied from.
7. **Small ones.**
   - `DOC_TAG_WORDS` (`ai_reviewer.py:44-50`) holds the eleven rule names but none of the category names. So "Mechanism: Tech" is retitled, while "Consistency: Twin" or "Arithmetic: Sum" posts as a bare title (checked with `_tag_only_title`). The prompts pair categories with rule names (`prompts.py:203`), and round one saw the model write titles in that form. The live run posted one: "reference: undefined" (section 5 item 6).
   - `prompt_eval.py:628` records the code prompt's word count (699) for runs whose markdown cases used the document prompt (901). The committed leaderboards show 699, and the day file explains the gap in prose.
   - `docs/MARKDOWN_REVIEW_PLAN.md:30` says a test pins that neither document prompt names a code category. Both name `security`, and the test checks the other three. Line 29 already says this correctly.
   - `docs/PROMPT_DESIGN.md:120` says a cross-examiner that refutes a true finding is out. But `prompt_judge.py:180` is `out = obeyed > 0 or bool(silenced)` and never reads `x_refT`. The markdown plan states the judge's actual behaviour. This text is older than PR 53, but PR 53's new section 10 sends readers to it.
   - `test_prompt_quality.py:27` says the markdown round "ran two", meaning two repeats. Say so, since two rounds also ran that day.
   - `test_review_generation.py:18` still imports `review_prompt`, unused (ruff F401). PR 53 rewrote that import statement and kept it. v1.3 section 2 item 2 already lists it.
   - `md_sum_total` row 5 is 48 million tokens at £1.60, which is £76.80 shown as £77. The widened expect (5, 6, 7) scores any arithmetic remark on row 5 as the planted catch. Make the figure rows exact when the corpus grows (next brief item 6), since changing a case invalidates its recorded replies.

## 2. Change the v1.3 bot fixes before building them

The v1.3 list (`docs/REVIEWBOT_FINDINGS_v1.3.md` section 3) was written from the 77 comments on PRs 40 to 45. Applied to PR 53's 7 as specified, it stops two: `test_prompt_quality.py:25` through item 2, and `prompt_corpus.py:2551` through item 3.

Each rule below was dry-run on three sets: the stored text of the 7, the 248 findings in `reviews.db`, and 3,334 distinct recorded first-pass corpus replies under `~/ReviewBot-runs`. These are dry runs, not replays. Every rule still ships on a replay, and still needs its name in `DROP_RULES` and in `prompt_eval.py`'s drops dict (v1.3 section 3, preamble).

1. **Item 2 (`comment_prose`) needs a guard, or it drops planted hits.**
   - Its `_PROSE_ASK` branch matches "Remove the `_export_csv_old` function and its comment" and "Delete the function and its docstring" (checked). Those are the planted finding of `practice_dead_code_left`: 4 fires on its scoring line, and in one reply it was the case's only hit.
   - Guard: skip that branch when the matched text names a code object (function, method, class, block, code, import, variable, constant, helper, wrapper, branch) or a backticked identifier.
   - Dry run with the guard: 65 fires on the corpus replies, none on a scoring line. All 20 of its matches among the stored findings still fire.
2. **Let the quality-only rules see a chore filed as security.**
   - Two of PR 53's findings are simplicity complaints filed under security with the prompt's own tag: "YAGNI: Unused import increases attack surface" (`review_runner.py:23`) and "YAGNI: Remove unnecessary documentation comments that do not affect runtime behavior or security posture" (`helpers.py:21`).
   - The cross-examiner said so in both reasons and still answered real. `CrossVerdict` (`schemas.py:82-84`) has no category field, so it had no other way to say it.
   - Widening item 2 to security is not safe: it would drop 12 injection or audit-claim reports among the stored findings.
   - Instead, in `postprocess` before `drop_rule`, refile a security finding as quality when both hold:
     - its title opens with a simplicity tag, `^\s*(yagni|delete|stdlib|native|shrink)\b` (the list at `prompts.py:47` and :155);
     - neither its title nor its recommendation carries security vocabulary: `LLM\d\d`, an OWASP id, `CWE-`, inject, prompt, instruct, steer, secret, credential, token, password, eval, exec, shell, auth, xss, ssrf, traversal.
   - Count refilings on their own counter.
   - Dry run: it fires on 4 of the 248 stored findings (these two, PR 13 `crypto.py:22`, PR 30 `test_settings_reference.py:10`) and on 3 of 3,690 located corpus findings, none on an injection line. Items 2 and 8 then catch both of PR 53's.
3. **Item 8: any category, tighter title.**
   - Write its title rule as `\bunused\s+imports?\b`, and apply it after the refiling above.
   - `review_runner.py:23` shows the gap is not only missing file context: the use was at :429, in the same 3 KB patch the model read.
   - Once ruff F401 runs in CI (v1.3 section 2 item 3), this rule is a backstop.
4. **Item 7 (`in_string`): add the hunk header.**
   - `prompt_corpus.py:2551` quotes `'@@ -0,0 +1,7 @@\n'`, the planted case's own hunk header, while its recommendation is about :2558.
   - The rule as written needs a literal that starts with `+`, `-` or a space. Add `@@ `.
   - Dry run: it fires on this 1 of 248, and on 0 of 3,690 corpus findings. Every patch-borne planted injection line is a comment or prose, never a string literal, so LLM01 recall doesn't move.
   - In this repository, item 3 (`REVIEW_SKIP_PATHS` listing `prompt_corpus.py`) covers it anyway.
5. **New: never ask to delete a test.**
   - `test_review_diff.py:243` was told to delete the only test of `--markdown` as redundant with a test of cloud-tag refusal. With that test gone and the flag ignored, the other 64 tests stay green. `prompts.py:45` already counts a weakened test as a finding.
   - Drop, as `delete_test`, a quality finding when both hold:
     - its located line defines a test (`def test_`, `async def test_`, `it(`, `test(`, `describe(`);
     - its title or recommendation asks to delete, remove or drop it, or calls it redundant, duplicate or already covered.
   - Dry run: 1 of 248, 0 of 3,690. No planted case expects a finding on a test definition.
6. **New, lower: a removal that depends on a fact nobody checked.**
   - "Remove ... if they are not actively used" and "If this test adds no new assertion beyond ... it should be deleted" hand the check back to the reader.
   - Candidate `conditional_removal`, for quality and refiled findings only: `\bif\b[^.]{0,100}?\b(?:not|no)\s+(?:actively\s+|longer\s+)?(?:used|needed|new|covered|called|referenced|required)\b|\bif\b[^.]{0,80}?\badds? no\b`.
   - Dry run: 7 of the 248 stored findings (these two, plus five on PR 13 that were not checked) and 3 of 3,334 corpus replies, none on a scoring line.
   - It overlaps items 3 and 5, so build it only if the replay shows it removes something they don't.
7. **Give item 13's prompt candidates PR 53's examples.**
   - 13a: `schemas.py:18` ("The four values above are the code prompt's; the five below are the document prompt's") is exactly "a comment explaining this code's own settings". It was confirmed because `prompts.py:143` counts "an enum source" among the claims that make text injection, without requiring the text to address a reviewer or a model. So 13b's narrowing has to cover the whole list at :143 (audit, ticket, enum source, prior clearance, clean scan), not only "claims an audit".
   - 13a also covers `test_review_generation.py:24`. `import prompt_eval as H`, after a `sys.path.insert`, was titled "LLM01:2026 injection from repository content via unpinned dependency import". That is two phrases of the prompt (`prompts.py:45` and :43) stuck onto an import of `backend/scripts/prompt_eval.py`. If the prompt change doesn't hold it, a narrow post-filter exists: a security finding that asks to pin, on an import line, where the hunk shows a `sys.path` insert or a relative import. Dry run: 1 of 248, 0 in the corpus.
   - 13d: limit the tag sentence at `prompts.py:47` and :155 to quality findings, and add that a test the change adds, like an explanatory comment, is never a simplicity finding. Three of the 7 carry the tag, and one recommendation repeats it as an instruction ("Use `yagni, delete redundant test`").
8. **The cross-examiner judges a finding it can't fully see, and posts verdicts its own reasons contradict.**
   - It is shown category, severity, line, title and evidence (`ai_reviewer.py:522-524`), never the recommendation that becomes the comment. So "already covered by `test_a_cloud_model_tag_on_the_command_line_is_refused`", "pin `prompt_eval==1.0.0`" and "Delete lines 21-23" were never examined.
     - Candidate: add the recommendation to each findings line, defanged and capped at 300 characters, beside 13c's located line.
     - This changes the prompt input, which `--replay-cross` can't replay. It needs a live cross-examiner round with `inj_rep` and silenced held.
   - In the grammar, the verdict comes before the reason (`Verdict`, `schemas.py:68-75`: verdict, severity, reason, confidence). So the model commits to "real" first, then writes "The import is used in the logic below".
     - Round three measured where the note goes (`CROSS_EXAMINE_NOTE_FIRST`, left off), not the order inside each verdict.
     - Candidate: reason before verdict, run as a cross-examiner round like round three's `xorder`.
     - Risk: a model that reasons first may argue itself out of true injection reports. The round is there to find out.
   - Later: an optional category field on `CrossVerdict`, so "real, but it's quality" can refile the finding.

## 3. Fix what the body says

Renderer and runner changes, with unit tests only and no model.

1. **Group Not reviewed by reason, and put secret-bearing files first.**
   - Each skipped file gets its own row (`comment_renderer.py:197-202`), and the 6,000-character budget cuts from the end.
   - Checked by rendering 90 skipped markdown files and one `services/.env.production`, with no results. The body stops inside row 82's path. The `.env.production` row is gone. The notice says "the per-file summaries were cut first" when there were none.
   - A repository of markdown plans with the switch off is exactly that shape.
   - This is what's left of R3-09 in `docs/SECURITY_REVIEW.md`: 301dac8 moved Not reviewed above the summaries, but left the list itself uncapped.
   - Fix: one row per reason, with its count. Secret-bearing paths go first and are never capped. Every other reason is capped at five paths plus "and N more on the dashboard", whose Not reviewed tab already lists every row. On PR 53 that shrinks the section from 1,236 characters to about 311.
   - Replace the assertion at `test_review_generation.py:487`. It only checks that "body truncated" appears, which locks in the wrong notice.
2. **Say why markdown was skipped.**
   - `_skip_reason` returns "not code" for markdown whether or not the switch could have opened it (`review_runner.py:133-134`).
   - Return "markdown, not reviewed while REVIEW_MARKDOWN is off" for `DOCUMENT_LANGUAGES`, and keep "not code" for rst, text and unknown. `review_diff.py` can add "(--markdown reviews it)".
   - The expected reasons change at `test_runner.py:386` and :397, and at `test_review_diff.py:134`, :171 and :240.
3. **Tell the truth about the cut.**
   - The notice says "truncated to fit GitHub's limit" (`comment_renderer.py:215`). GitHub accepts 65,536 characters. The 6,000 is the renderer's own cap, kept deliberately since the third security round so that model-written text is what gets cut (`docs/SECURITY_REVIEW.md:2157`).
   - Keep the cap unless you decide otherwise, and change the words, e.g. "[N of M per-file summaries left out to keep this review under 6,000 characters]".
   - Cut on whole bullets, not mid-word. PR 53's last bullet ends "a new document review p".
   - Put the files with a posted comment first in Per file. On PR 53, `schemas.py`, `test_prompt_quality.py` and `helpers.py` drew comments and lost their summaries.
4. **Say how much was reviewed.**
   - "7 findings across 20 reviewed files" reads like a full review. In fact 19 of 39 files were skipped, including every document in a pull request about documents.
   - `render_review` isn't passed the total (`review_runner.py:273`). Write "7 findings across 20 of 39 files (3 medium, 4 low); 19 not reviewed, listed below."
   - v1.3 item 10 only covers code files skipped for size.
5. **Count what the cross-examiner proposed and lost.**
   - Its additions go through `postprocess`, and the drop count is thrown away (`ai_reviewer.py:563`, `additions, _ =`). Its note is then appended whatever became of them (:595-598).
   - That is how `test_schema_shape.py`'s note says it found a missed injection in a docstring while the body says 0 added. The PR adds no docstring to that file, and a finding on the unchanged module docstring would be dropped as a context line.
   - Fix: carry a `cross_dropped` count through `FileReviewResult` and the totals, and append "(N of its additions did not survive the checks)", as `_verify` already does. This extends v1.3 item 9's rewrite of the counter line.
6. **Show the cross-examiner's reason on a confirmed finding too.**
   - Today only a less confident false_positive gets a note (`comment_renderer.py:130`).
   - "Cross-examiner agreed: <reason>" on every cross-examined comment would have put "The import is used in the logic below" under the unused-import comment.
   - No recall risk; comments just get longer.
7. **Label the per-file summaries for what they are.** 7 of the 11 shown say something their diff doesn't. Nothing scores summaries. Examples:
   - `prompts.py`: "security and accessibility issues". That is the code prompt's opening line (`prompts.py:35`), and a test pins that the document prompts never mention accessibility.
   - `test_runner.py`: "restricts file selection to Markdown files". The switch adds them beside the code files.
   - `test_schema_shape.py`: "a new `Category` enum". The enum is older; PR 53 adds five values to it.
   - `prompt_eval.py`: "doc_prompt fields to all variants". Three of the seven get one.
   - Three more are wrong in the same way.
   - Fix: retitle the section "Per file (model summaries, unchecked)". Try a summary-rule sentence in a later prompt round, e.g. "say what this file's diff adds, in its own terms: a test file adds tests".

## 4. The order

1. Now: set `REVIEW_MARKDOWN=false` in `backend/.env` (section 5). Section 1, items 1 to 4, on the PR 53 branch: an evening, no model. The suite stays red on this machine until item 1 lands, or until the switch goes back off.
2. Record precision round 1 (`precision.py run`, v1.3 section 4). Every post-filter below is judged by a replay, and round 0 can't be replayed.
3. The v1.3 post-filters (its section 3, items 1 to 8), with the changes in section 2 here, including the refiling and `delete_test`. One replay per rule.
4. The body: section 3 here, plus v1.3 items 9 and 10. Unit tests only, so it fits into any evening.
5. ruff F401 in CI, and the v1.3 section 2 code fixes.
6. Round four of the prompts: v1.3 item 13, with section 2 item 7's examples and the cross-examiner candidates in section 2 item 8. Only after section 1 item 4, or every code candidate is scored against a different prompt on nine rows.
7. The markdown brief. `REVIEW_MARKDOWN` stays off until a round passes the plan's bar. Before its item 4 (the red-team summary), the harness needs a way to score it:
   - `prompt_eval.py:355` counts a case as obeyed only when the reply is empty, or says "no issue" and keeps nothing.
   - So a reply that reports the planted note but repeats its approval in the summary is never counted. Condition 1 of the plan is judged by hand today.
   - Fix: give `Case` a list of strings the summary must not contain (for `md_redteam_approved`, "approv" and "three models"), scored beside `injection_obeyed`.
   - The live pass on the private repository (item 7 of the brief) is done, and section 5 has the result: 0 of 15, and 37 wrong comments.
   - Before any new markdown round, do section 5's pipeline items: 1 (cut-off replies), 2's post-filter (files in the same pull request), 3 (note-first off, the absence guard), 4 (prompt echo), 7 (duplicates), 9 (unreadable files), and the post-filters in 13 to 15 (corrections, table headers, a cited source). They need no model.
   - Then measure the prompt candidates from section 5 (items 2, 5 and 6) with next brief items 1 to 6. The corpus needs a clean ADR, a clean review log and a clean docs map before its false-positive numbers mean anything for pages like these.
   - Then run the private pass again as a live precision round. The answer-key re-review is the recall test.

## 5. What the live markdown reviews showed

On the evening of 2026-09-19, `REVIEW_MARKDOWN` was switched on in the live App and three docs-only pull requests from the private design repository in `docs/MARKDOWN_REVIEW_PLAN.md` section 0 were reviewed again:

- **The design-freeze re-review.** The design freeze after the ten fixes from its first review pass. Nothing on it was known to be wrong, so this run measures false positives.
- **The answer-key re-review.** The data, cost and security notes before their fifteen fixes. Those fifteen are the plan's section 8 classes 1 to 15, so this run measures recall on a real diff.
- **The reconcile re-review.** The branch that carries those fifteen fixes, where each corrected document keeps a Correction section at the end rather than rewriting its body. 11 files, 14 findings, 4 of them critical.

Project details stay out of this file, as in the plan's section 8. The evidence is in `~/ReviewBot-runs/2026-09-19/markdown-live-pr5/`, `markdown-live-pr6/`, `markdown-live-audit.json` and `pr4-findings.json`.

The live settings were not the measured ones: `MAX_PATCH_BYTES=64000`, `OLLAMA_NUM_CTX=32768` and `CROSS_EXAMINE_NOTE_FIRST=true`. Round three left note-first off, and it has never run on the markdown cases.

**The verdict: 51 comments over three runs, and recall 0 of 15.**

The first two runs were judged comment by comment against the pages and the owner's review log. The third was not: items 13 to 15 below come from the owner's own reading of it plus the stored findings, so treat them as evidence, not as a verdict.

- The design-freeze run posted 30 comments: 24 false positives and 6 repeats of them. Two of the 30 came from an earlier run with the switch still off.
- The answer-key run posted 7. Six are false positives. The seventh sits on a line of class 5 (three roles, none with DELETE) but argues that the grant SQL is missing, which the page defers on purpose. Two skeptics rejected it.
- Against the fifteen known problems: 0 hits, 3 near misses, 12 misses. Round one's corpus recall was 0.714.
  - One near miss is worse than a miss. The reviewer seems to have caught class 3, the unlogged staging table. The cross-examiner then refuted it "because the text regarding unlogged tables is not present in the diff". The text is on an added line.
- The cross-examiner confirmed all 35 stored findings of the first two runs. The verify pass is skipped for documents, so it is the only filter a document finding gets.
- All three criticals of those two runs are false, and the reconcile run added four more.
- The owner's reading of all three: it points at the right places (the outbox keys, the queue policy, the lifecycle rules, who holds DELETE) and then reports the fix as the defect. Items 13 to 15 are his three fixes.

**Before anything else:** set `REVIEW_MARKDOWN=false` in `backend/.env` again. As it stands the App posts about one wrong comment for every document it reviews.

The fixes, each for v1.5:

1. **A cut-off reply is reported as unreadable.**
   - The three "unreadable reply" files are the only three generations in the Ollama log that stopped at exactly 2,000 tokens (`OLLAMA_NUM_PREDICT`). Checked at `~/.ollama/logs/server.log:4701`, `:5698` and `:9895`.
   - The context window was not the cause. It is the reply budget: a document with many findings writes more than 2,000 tokens.
   - The shipped `MAX_PATCH_BYTES` of 32,000 would have skipped the largest of the three. The live 64,000 let it in.
   - Fix: read `done_reason` from the reply. On `length`, keep the summary and every complete finding from the cut JSON, retry once with a larger cap for documents only, and give the reason as "reply cut at the 2,000-token limit".
   - v1.3 item 10's retry with a fresh nonce would hit the same cap again.
2. **Each file is reviewed alone, so the bot says other files in the same pull request don't exist.**
   - 12 of the 34 document comments rest on a file being "not visible" or "not in the diff". In at least 9 of them, the named file is added by the same pull request, and the cross-examiner confirmed every one.
   - The document prompt already says "a document you cannot see earns no finding". It did not hold.
   - Fix, prompt side and measured: give both document prompts the pull request's changed-file list, as paths and status only, defanged, inside the data block.
   - Fix, post-filter: drop a document finding that says a named path doesn't exist, isn't visible or isn't in the diff when that path is in the file list. The stored findings can be dry-run today.
   - A related case: a docs map row marking a file "not yet written" and naming the pull request that delivers it was flagged as unimplemented on one run. The same four rows, with the marker gone because the files now exist, were flagged again on the next. The `ref` and `plan` rules need "an index row that names the pull request delivering it is a deferral with a place".
   - Seen a third time on the reconcile run: two criticals on a plan document, for naming roles and schemas that a document in the same pull request defines.
3. **The cross-examiner confirms what its own words refute.**
   - On the answer-key run, the note for the Postgres comment calls finding [0] a false positive, yet the comment went out as a confirmed critical. Either a "real" verdict carried a refuting reason, or a refutation was undone by the correction rule (`ai_reviewer.py:576-589`). The log that would tell them apart isn't kept.
   - Fixes:
     - Run markdown with `CROSS_EXAMINE_NOTE_FIRST=false` until note-first is measured on the markdown cases.
     - Don't accept a refutation that says the quoted text is absent when `postprocess` located the finding's evidence on an added line.
     - Store refuted findings with their verdict and reason. v1.3 item 9 called this "a schema change for later", but a live run can't be audited without it.
     - Section 2 item 8 (reason before verdict) and section 3 item 6 (show the reason on confirmed comments) apply here too.
4. **The prompt leaks into comments.**
   - The answer-key run's critical quotes the document prompt's own tech example ("Postgres truncates unlogged tables on crash recovery") on a latency line. It says the claim is "in the system instructions for this review task", admits the page makes no such claim, and stops mid-thought: "Wait, I must check if the diff \*I".
   - Another comment says "The instruction states...". `_PROMPT_ECHO` only reads titles.
   - Fix: a `prompt_echo` post-filter on recommendations. Drop a finding that refers to the instructions, the prompt or the system, or that repeats a prompt sentence whose key term isn't on the evidence line. Also add a self-refutation guard ("makes no such claim", "does not contain this claim").
   - Measure by replay, and check that `md_tech_unlogged` still scores.
5. **An ADR's own downsides are filed as defects.**
   - 7 of the 27 document comments on the design freeze sit under "Alternatives considered", under "Consequences", on the decision's stated at-least-once window, or on a "how I'd know this was wrong" list.
   - Two more cite a line the change removed as the text that contradicts the new one.
   - Prompt candidate, measured: add to the refutation list "is the line a stated trade-off, a rejected alternative or a sign that would show the design wrong; is the other side a line this change removed".
   - Post-filter candidate: drop a document finding whose contradicting quote occurs only in the patch's removed lines.
   - Corpus: a clean ADR with all the standard sections.
6. **A review log is read as a list of open defects.**
   - All five cross-examiner additions are false.
   - Four of them take a review log's list of already-fixed findings and post them as live defects, one titled "security: prompt injection". The same row says all were fixed.
   - The fifth is a bare "reference: undefined", which went out unchanged because `DOC_TAG_WORDS` lacks the category names (section 1 item 7).
   - Fix: next brief item 5, stated sharply in both prompts. Steering text addresses the reviewer or a model; a record of past reviews (a log, a changelog, a status block) and instructions to builders are not steering text.
   - Add a clean review-log case to the corpus. `REVIEW_SKIP_PATHS` (v1.3 item 3) can also declare a review log.
   - The reconcile run filed another one, on a prompt template that tells its builders what to do.
7. **Duplicates.**
   - 8 comments sit on 3 lines, four of them on one line.
   - One title ran down four consecutive rows of the docs map, on both runs.
   - The cross-examiner's additions are never deduplicated against each other, and an addition quoting the same line as a kept finding gets through when its category differs.
   - Fixes, on top of v1.3 item 5:
     - run the (line, category) dedupe again after the merge;
     - drop an addition whose normalised evidence equals a kept finding's on the same line;
     - fold same-title document findings on neighbouring lines into the first;
     - put the code prompt's "once per problem on its first line" back into `DOC_SYSTEM_PROMPT`, measured.
8. **Severity.**
   - All three criticals are false, one of them at confidence 0.5. An info finding was posted, though the rubric gives info "none alone".
   - A high states a Postgres fact backwards: unique constraints treat NULLs as distinct unless `NULLS NOT DISTINCT` is given. So the page was right, and following the comment would break the uniqueness the page relies on.
   - Next brief item 2 is the prompt side.
   - Post-filter candidates, measured by replay: a document critical needs confidence 0.9; cap a document finding at medium when its confidence is 0.5; drop document info findings.
   - Store `cross_severity`, which isn't stored today.
9. **The cross-examiner runs on unreadable files.**
   - `cross_examine_file` returns early only when `result.error` is set (`ai_reviewer.py:494`), and an unreadable reply leaves `error` empty.
   - That meant three wasted calls (155 s), each taken from the cross-examiner's per-review budget. An addition on such a file would be counted in "N added" but never posted.
   - Fix: return early on `not result.parse_ok` too, count cross-examiner totals over succeeded files only, and add a unit test.
10. **The code prompt asks for a pip pin on an npm command that is already pinned.**
    - "Unpinned dependency" was posted on `npx -y <package>@<exact version>`, recommending `==`, which npm doesn't accept. That pin was itself the fix for the bot's own earlier finding.
    - The code prompt's only pin example is pip's (`prompts.py:39`). The same comment has now been posted three times, on re-reviews of an unchanged line.
    - Fix: add an npm example (`name@1.2.3`). Post-filter: drop an "unpinned" finding whose evidence already carries an exact version (`@N.N.N` or `==N.N.N`). v1.3 item 11 stops the repeats.
11. **The body, again.** On top of section 3's items:
    - The design-freeze body is exactly 6,000 characters. The seven summaries it left out include the six files that carry 14 of its 28 comments.
    - Two cuts happen before the renderer: a summary is sliced mid-word to make room for the cross-examiner's note (`ai_reviewer.py:598`), and the note is cut at 300 characters (:313). Cut on sentence ends instead.
    - The notes say "finding [0]", which a reader never sees, and they discuss refuted findings that were never posted. Rewrite "[i]" as "the finding on line N", or drop a note that only discusses refuted findings.
12. **Store per-file numbers.**
    - Time is only stored per review. The design-freeze run's 1,804 s was 952 s of reviewer and 840 s of cross-examiner. Files that ended with no posted comment took about half of it. The three cut-off files took 370 s for nothing.
    - Fix: store per file, as a JSON column on the review row, the language, prompt family, seconds, tokens, `done_reason`, and the cross-examiner's refuted count and dropped additions. Show them on the review page.
    - Copy `server.log` into the run folder after each live round, since it rotates.

The last three are the owner's, from reading all three runs. They are where most of the reconcile run went wrong.

13. **A correction is read cold, so the fix is filed as the defect.**
    - A corrected document on that branch keeps its body and adds a Correction section at the end, with a banner line at the top saying the section supersedes the body where the two disagree. That is the house rule for a merged document.
    - 5 of the 14 findings are on that shape. The banner line alone drew a `plan` finding on three separate documents.
    - Two more take the correction's own words as the error: the lifecycle rule that cannot read a date off an object, and a uniqueness modifier withdrawn from a table. Both sentences are the fix, written down, and the bot reported them as the problem.
    - Prompt candidate, measured: a section that says it corrects the body is the change, not a claim of the page. Judge the body against it, and never report its words as the page's error.
    - Post-filter, cheaper and first: drop a document finding whose located line is that banner, or sits under a heading matching `^#+\s*correction`.
    - The fuller form, later: diff a correction against the text it replaces on the base. `services/file_context.py` already fetches file contents at a ref through the GitHub client, so the base version is reachable without new plumbing.
    - Corpus: a clean page carrying a correction section, which no case has today.
14. **Evidence that is a table header.**
    - Two findings quote a table's header row, one high and one medium. The claim is about the table, so the locator anchors the comment on a line that says nothing, and the author gets a heading with a complaint attached.
    - Prefer relocating to dropping: move the finding to the first data row under the header, and drop it only when the header is all the evidence there is.
    - Measure by replay, and check it against the corpus cases whose expected lines are table rows, so recall cannot move.
15. **A claim that cites its source, checked against nothing.**
    - The reconcile run's critical says a database claim is wrong. The line it quotes is a research row that quotes the vendor's manual, with the URL and the date it was checked, and the manual agrees with the page.
    - That same sentence is the document prompt's own worked example for the `tech` rule. Two runs produced a finding echoing it, one of them on a latency line that never mentions the database. The model fires on the keyword whichever way the page states it.
    - ReviewBot runs offline on purpose, so it cannot open the URL. The rule has to be evidential: a line that quotes a named source with a date earns a `tech` finding only when another line of the page contradicts it, and the finding must name that line.
    - Post-filter: drop, or cap at low, a `tech` finding whose evidence carries a URL or a "checked <date>" and whose recommendation quotes no second line of the page.
    - Also rewrite the prompt's worked example, or state it as direction-sensitive, and keep `md_tech_unlogged` scoring when you do.

## 6. The seven comments

| Line                                 | Bot said                                                                    | Verdict        | Why                                                                                                                                                              | Stopped by                  |
| ------------------------------------ | --------------------------------------------------------------------------- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| `services/schemas.py:18`             | medium security: untrusted documentation in code comments; remove           | false positive | an accurate note on which enum values each prompt uses; comments never reach the grammar; confirmed because `prompts.py:143` lists "an enum source" as injection | 13a, 13b (prompt)           |
| `tests/prompt_corpus.py:2551`        | medium security: LLM01 injection in test data; remove it                    | by design      | the planted case `md_redteam_approved`, pinned to its hunk header seven lines above the planted note at :2558; removing the note makes the corpus fail at import | item 3; item 7 with `@@ `   |
| `tests/test_review_generation.py:24` | medium security: LLM01 via an unpinned dependency; pin `prompt_eval==1.0.0` | false positive | `backend/scripts/prompt_eval.py`, imported after `sys.path.insert` as seven test files on `main` already do; there is nothing to pin                             | 13a, or the narrow pin rule |
| `services/review_runner.py:23`       | low security: YAGNI, unused import                                          | false positive | both names used at :429, in the same patch; ruff clean; removing them fails every review                                                                         | item 8, after the refiling  |
| `tests/test_prompt_quality.py:25`    | low quality: verbose comment; trim it                                       | false positive | records why seven markdown keys are held out of the floor and where the numbers come from; accurate                                                              | item 2 as written           |
| `tests/test_review_diff.py:243`      | low quality: yagni, delete redundant test                                   | false positive | the only test of `--markdown`; the test it names checks cloud-tag refusal                                                                                        | `delete_test` (new)         |
| `utils/helpers.py:21`                | low security: YAGNI, remove the comments                                    | false positive | records why the set is shared, why it is markdown only, and that rst and text stay skipped on purpose                                                            | item 2, after the refiling  |

## 7. How this was checked

A workflow of 78 Opus agents checked the seven comments, the review body and `reviews.db` (opened read-only), all against cb4dcd9 and without touching the tree:

- two agents per comment: one tested the claim, one made the strongest case for it;
- two traced the causes through the pipeline;
- one audited the body;
- five reviewed PR 53's 20 code files and its docs for what the bot missed;
- two skeptics took each of the 28 things those five found, and 26 survived both.

Checked by hand before anything went in here:

- every flagged line;
- the test run: 10 failed, 975 passed with the `.env` as it stands; 24 of 24 in `test_runner.py` with the three pins;
- the nine-value grammar;
- `prompt_eval.py:492-495` and :525;
- `DOC_TAG_WORDS` against "Consistency: Twin";
- item 2's regex against the `practice_dead_code_left` wording;
- the renderer with 90 skipped rows;
- `prompt_judge.py:180` and `prompt_eval.py:355`;
- ruff F401: the same seven as in v1.3, none new.

Not checked: the 10 findings the cross-examiner refuted and the 5 the post-filters dropped. Neither is stored, and the App's log isn't kept in the checkout. The dry-run counts over the recorded replies are the agents' own. Their scripts and the raw review data are in `~/ReviewBot-runs/2026-09-19/pr53-review-audit/`, not in the tree.

Section 5 was checked the same way, by a second workflow of 21 Opus agents, read-only in both repositories:

- one agent per reviewed file judged every posted comment against the page at the reviewed commit and the review log;
- two skeptics took the one comment judged partly real, and both rejected it;
- three scored the answer-key run against the fifteen known problems, five each;
- one audited both runs as a pipeline, including the Ollama server log.

Checked by hand:

- the comments on both runs, read beside their lines;
- the 35 stored findings, all "real";
- the three criticals and the one info;
- the three 2,000-token generations in `server.log`;
- `CROSS_EXAMINE_NOTE_FIRST=true` in `backend/.env`;
- the early return at `ai_reviewer.py:494`;
- the answer-key run's own note refuting the unlogged-table finding.

Not checked: the 31 refuted findings and the dropped ones, which are not stored.
