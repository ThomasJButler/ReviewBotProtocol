# What it catches, what it misses, and which of that is the model

Written 2026-09-08, from the first night this bot was pointed at real pull requests rather than a corpus of planted diffs.

Everything in `docs/benchmarks/` measures recall: a diff with a known bug in it, does the reviewer find the bug. That is worth measuring and it is not what a reviewer is for. A reviewer is read by a person deciding where to spend an hour, and the number that decides whether they keep reading is precision: of the findings it posts, how many are worth acting on. This file is the first measurement of that, what it says, and what to do about it.

The question this is organised around is Tom's: for each weakness, would a bigger or a cloud model have caught it anyway, or is it the harness, in which case no model gets you out of it. That matters because the plan is to keep running local models as they improve and to reach for cloud when it earns its place. A list that is only a snapshot of one 9B is worth little.

## The measurement

On 2026-09-07 the eleven v1.2 pull requests were reviewed by the live App with `qwen3.5:9b` reviewing and `gemma4:12b` cross-examining, sequentially, `VERIFY_FINDINGS` off, `MAX_FILES_PER_REVIEW` 50, 16k context. Ten reviews had completed when the count below was taken, in 41 minutes of laptop.

Three independent readers went over the same code that night. They agree on nothing.

| Reader                                                    | Findings | Worth acting on |
| --------------------------------------------------------- | -------- | --------------- |
| ReviewBot (`qwen3.5:9b` plus `gemma4:12b`)                | 22       | 0               |
| A Claude-driven pre-merge review of the same eleven diffs | 9        | 9               |
| A Claude Security scan of the same range                  | 2        | 2               |

Not one of ReviewBot's 22 overlapped with the eleven real defects the other two found. Two of those eleven were in code ReviewBot had reviewed and reported on: it read the retention sweep and did not notice that deleting the delivery records reopens the webhook replay window, and it read the praise rule and did not notice that its own regex could be made to stall the event loop for 84 seconds.

The precision number was obtained by putting every one of the 22 findings to two independent judges, each reading the actual code, each asked to say whether a competent maintainer would change anything because of it. Forty-four judgements, unanimous. The method is repeatable and is what the recommendations below propose to keep doing.

## Where the errors came from

Each of the 44 judgements classified the failure. The last column is the answer to the question that matters.

| Why it was wrong                         | Votes | Would a better model fix it                                                                                                                                                                                                     |
| ---------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Factually wrong about the code           | 19    | Partly. The model asserted things about imports, callers and identifiers it could not see, because it is only ever shown one diff hunk. A cloud model behind the same blindfold guesses too; it hedges more. **Harness first.** |
| Style preference, no defect              | 11    | Mostly yes. Both prompts already forbid it and the model files it anyway, which is instruction-following. **Model, with pipeline rules as the cheap interim.**                                                                  |
| About a line the change never touched    | 7     | No. The pipeline decides what counts as in scope, and it currently accepts context lines as evidence. **Harness, entirely.**                                                                                                    |
| Read a defence as the attack             | 5     | Yes. Judging that a redaction pattern is the redaction and not the injection is exactly where model quality shows. **Model, plus a corpus that contains the shape.**                                                            |
| Title was the reviewer's own instruction | 2     | No. Fixed in the pipeline the same night. **Harness, done.**                                                                                                                                                                    |

So about 26 of the 44 are harness problems that no model size resolves, 16 are model or prompt, and 2 are already gone. That ratio is the single most useful thing in this document: most of tonight's noise is fixable without waiting for better weights, and the parts that are not are identifiable.

## What to do, in the order I would do it

**1. Measure precision every round, not just recall.** Nothing in the harness scores a real pull request, because a real one has no answer key. The method above supplies one: review a fixed set of real pull requests, judge every finding independently against the code, record one number. Without it a prompt that raises recall can quietly cost precision and the leaderboard would show only the gain. _Harness. Costs an afternoon to set up and an hour a round._

**2. Show the model the file, not only the hunk.** Nineteen of the 44 wrong votes were claims that the diff alone cannot settle: an import called unused when it is used four lines below the hunk, a component called dead when its caller is in the same file. Send the whole file when it fits the remaining context, else a window of N lines around each hunk, and say in the prompt which part is the change. This is the biggest single lever in the list and it is pure harness: it costs context and seconds per file, both measurable, and it makes every model better at once. _Harness. An evening, plus a measured round._

**3. Treat a context line as weaker evidence than an added line.** Seven votes were findings about lines the pull request never touched. `services/diff.py` already separates `added_lines` from `new_lines`, so the pipeline can require higher confidence, lower the severity, or drop such a finding outright in a change review. Measure the three options by replay before choosing. _Harness. An evening._

**4. Give the corpus the shapes this codebase is made of.** All five defence-read-as-attack findings landed on a redaction pattern, a test fixture holding a hostile string, or a docstring quoting an attack. A security tool is mostly made of that, and the corpus contains none of it, so no prompt has ever been scored against it. Add a dozen clean diffs of that shape, then judge a rule that downgrades a security finding whose evidence is a comment or a fixture. Do the corpus first: a rule written without it is a guess. _Corpus, then harness. The corpus work is already in the roadmap._

**5. Spend the verify pass where the errors are.** `VERIFY_FINDINGS` is measured and off because it costs a call per finding across the whole review. Twelve of tonight's 22 were filed as security, which is the class most often wrong and the class a reader trusts most. Running the verify pass on security findings alone puts the cost where the damage is. _Harness knob, already built. An hour, then measure._

**6. Then, and only then, ask whether the model is the limit.** After 2, 3 and 5 land, re-run the precision measurement unchanged. What is left is the model's share: on tonight's split, the 11 style-preference and 5 defence findings. Compare three ways on that same number, not on recall: `qwen3.5:9b`, a larger local model on a machine that can hold it (the 30B in `docs/HOSTED_MODEL_PLAN.md`), and a cloud model as the ceiling. That gives a per-model precision figure and turns "are local models good enough yet" into a number you can re-run each time a new one lands. _Model. One evening per model once the measurement exists._

## Two things to keep in mind while reading any of its output

**A finding is the unit of trust, not a review.** Three consecutive reviews of pull request 13 on the same code shared about two findings by title out of thirty. Consistency between runs is low, which means an empty review is weak evidence of a clean diff and a single finding is worth reading on its own merits rather than as part of a verdict.

**High recall on planted bugs and zero precision on reviewed code are both true at once.** The corpus number (0.98) says the reviewer will usually notice a bug someone planted for it. Tonight's number (0 of 22) says that on small, careful, already-reviewed diffs it currently produces nothing worth acting on. Neither number is wrong; they measure different things, and the README should say both.

## Provenance

Every number here is reproducible. The corpus figures come from the leaderboards under `docs/benchmarks/runs/2026-09-07/`, regenerated by the commands in `docs/benchmarks/2026-09-06-round-three.md`. The 22 findings and their categories are the rows in `reviews.db` for pull requests 23 to 32, readable through `GET /api/reviews`. The nine real defects are the commits on the eleven v1.2 branches whose messages name what the pre-merge review found. The two vulnerabilities are `CLAUDE-SECURITY-20260908-004806`, which is gitignored by default and can be read in place.
