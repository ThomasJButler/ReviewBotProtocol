# Precision, round0

`scripts/precision.py score` over 11 pull requests of the fixed set in `backend/tests/precision/pull_requests.json`, judged per finding in `backend/tests/precision/judgements.json`. The protocol is [../../PRECISION.md](../../PRECISION.md).

| Round  | Findings | Distinct | Judged | Real | Disputed | Precision |
| ------ | -------- | -------- | ------ | ---- | -------- | --------- |
| round0 | 22       | 22       | 22     | 0    | 1        | 0.00      |

Why the rest were wrong, one vote per judge per finding:

| Why               | Votes |
| ----------------- | ----- |
| real              | 1     |
| wrong about code  | 16    |
| style preference  | 15    |
| untouched line    | 2     |
| defence as attack | 3     |
| instruction title | 2     |
| other             | 5     |

Per pull request:

| PR  | Files reviewed | Findings | Judged | Real | Precision |
| --- | -------------- | -------- | ------ | ---- | --------- |
| 23  | 0              | 0        | 0      | 0    | n/a       |
| 24  | 16             | 4        | 4      | 0    | 0.00      |
| 25  | 5              | 0        | 0      | 0    | n/a       |
| 26  | 5              | 4        | 4      | 0    | 0.00      |
| 27  | 10             | 0        | 0      | 0    | n/a       |
| 28  | 4              | 2        | 2      | 0    | 0.00      |
| 29  | 12             | 6        | 6      | 0    | 0.00      |
| 30  | 3              | 4        | 4      | 0    | 0.00      |
| 31  | 7              | 2        | 2      | 0    | 0.00      |
| 32  | 0              | 0        | 0      | 0    | n/a       |
| 33  | 2              | 0        | 0      | 0    | n/a       |

Model `qwen3.5:9b`, cross-examiner `gemma4:12b`, pipeline a11f356ec5fc. The raw records, with every model reply, are kept outside the repository under `~/ReviewBot-runs/<date>/precision-runs/`.
