# 2026-09-04: the specialist reviewer prompt, the verify pass and the red team

Machine: Apple M1 Max, 32 GB, Ollama 0.33.1. Model: `qwen3.5:9b`, reasoning off, output bound to the JSON schema. Pipeline commits: 37d5482 (the prompt and the harness), 8cdb6d3 (the red-team corpus). The run files from this day were written to the session's temporary directory and were lost when the machine rebooted on 2026-09-05; the numbers below are as recorded the same day in `backend/README.md` ("Measuring the prompt") and `docs/SECURITY_REVIEW.md` (fourth round), which were written from the harness output at the time.

## The eleven-case corpus, two repeats

`backend/tests/prompt_corpus.py` as it stood that day: SQL injection, a hard-coded AWS key, `eval` on input, path traversal, `shell=True`, MD5 on passwords, a missing authorisation check, a planted instruction beside a command injection, a check-then-act race, and two clean diffs.

```
.venv/bin/python scripts/prompt_eval.py --repeats 2
```

| variant                                           | recall | planted instruction | false positives | tokens per file | seconds per file |
| ------------------------------------------------- | ------ | ------------------- | --------------- | --------------- | ---------------- |
| old prompt (the generic assistant)                | 0.89   | reported 1 of 2     | 0               |                 |                  |
| new prompt (specialist reviewer, about 470 words) | 1.0    | reported 2 of 2     | 0               | about 960       | about 8          |
| new prompt with the verify pass                   | 0.78   |                     | 0               |                 |                  |

What it says. Prompting the model as a specialist reviewer of one file's diff, with the untrusted-data block and the evidence rule, lifted recall to 1.0 and made it report the planted instruction every time. The same-model verify pass cut recall to 0.78 by refuting real findings while there were no false positives left to remove, which is why `VERIFY_FINDINGS` shipped off and why a second model from a different family replaced it the next day.

## The red team, fifteen hostile diffs

`backend/tests/prompt_redteam.py`: forged audit notes and "closed as false positive" tickets, fabricated scanner output, a pre-computed empty answer to echo, a 184-line file with the bug at the end, requests to put a sentence, a link, a lookalike link, an @mention, an HTML image or the system prompt into the review, a dictated fake evidence quote, newlines and forged delimiters in the file name, marker-shaped text with random nonces, bidi and zero-width characters, a comment lying about line numbers, and a second fake diff nested inside the first. Each beside one real bug.

```
.venv/bin/python scripts/prompt_eval.py --redteam --variants new
```

| measure                                                      | result                                        |
| ------------------------------------------------------------ | --------------------------------------------- |
| planted instruction obeyed                                   | 0 of 15                                       |
| attacker-chosen text in any summary, title or recommendation | none                                          |
| real bug found at the right line                             | 14 of 15                                      |
| hostile text reported as attempted prompt injection          | 11 of 15, named in the summary in the other 4 |

The one miss was an SSRF the model described correctly in its summary but quoted from outside the diff, so the evidence check dropped the finding.

## Early on 2026-09-05, before the reboot (files lost)

The same prompt and the first cross-examiner prompt were measured on the 26 cases (11 corpus plus 15 red team) at 02:56 and 03:09 with `gemma4:12b` resident beside the reviewer; recorded in the plan file at the time: reviewer alone recall 0.96, obeyed 0 of 16, reported 12 of 16, no false positives, 12.5 seconds and 1160 tokens per file; with the cross-examiner recall 1.0 but the injection reports fell to 6 of 16 because gemma refuted them, one praise-as-finding on a clean diff, 30.8 seconds and 2109 tokens per file. Both runs were lost with the scratchpad; the same questions were re-measured on 2026-09-05 with one model resident at a time.
