"""What PROMPT_OVERHEAD_TOKENS in services/review_runner.py should be for a
measured prompt.

usage: .venv/bin/python scripts/prompt_overhead.py <run json from prompt_eval --out> <cases json>

For every row: overhead = the prompt tokens Ollama counted minus the runner's
own estimate of the redacted patch (bytes / BYTES_PER_TOKEN). The constant
must cover the largest overhead seen plus headroom, or _fits_context admits
patches that no longer fit num_ctx. The two constants are read from the
runner's source so this needs no Settings environment.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.redaction import redact_text  # noqa: E402

_SRC = (Path(__file__).resolve().parents[1] / "services" / "review_runner.py").read_text(encoding="utf-8")
BYTES_PER_TOKEN = float(re.search(r"^BYTES_PER_TOKEN = ([\d.]+)", _SRC, re.M).group(1))
PROMPT_OVERHEAD_TOKENS = int(re.search(r"^PROMPT_OVERHEAD_TOKENS = (\d+)", _SRC, re.M).group(1))


def main(argv) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    run = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    cases = {c["key"]: c for c in json.loads(Path(argv[2]).read_text(encoding="utf-8"))}
    seen = []
    for r in run["rows"]:
        case = cases.get(r["case"])
        if not case or not r.get("prompt_tokens"):
            continue
        est = len(redact_text(case["patch"]).encode("utf-8")) / BYTES_PER_TOKEN
        seen.append((r["prompt_tokens"] - est, r["case"], r["prompt_tokens"], round(est)))
    if not seen:
        print("no rows with prompt tokens matched the cases")
        return 1
    seen.sort(reverse=True)
    print(f"variant {run['variant']} ({run.get('prompt_words')} words), {len(seen)} rows, current constant {PROMPT_OVERHEAD_TOKENS}")
    print(f"overhead: max {seen[0][0]:.0f}, median {seen[len(seen) // 2][0]:.0f}, min {seen[-1][0]:.0f}")
    for over, key, ptok, est in seen[:5]:
        print(f"  {key:<32} prompt_tokens={ptok:<6} patch_estimate={est:<5} overhead={over:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
