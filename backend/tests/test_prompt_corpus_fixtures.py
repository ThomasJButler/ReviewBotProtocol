"""The planted corpus is checked in the default suite, model-free: every
expected line is really in its diff, hunk headers add up, and no
token-shaped literal sits in the source file."""

import re
from pathlib import Path

import pytest

from services.diff import parse_patch
from services.redaction import redact_text
from tests.prompt_corpus import CASES, CASES_BY_KEY
from tests.prompt_redteam import REDTEAM_CASES

ALL_CASES = CASES + REDTEAM_CASES


@pytest.mark.parametrize("case", ALL_CASES, ids=[c.key for c in ALL_CASES])
def test_ground_truth_lines_are_in_the_diff(case):
    parsed = parse_patch(case.patch)
    for line in case.expect + ((case.injection_line,) if case.injection_line else ()):
        assert parsed.is_commentable(line), f"{case.key}: line {line} is not in the diff"
    if case.clean:
        assert not case.expect
    else:
        assert case.expect and case.min_severity in ("medium", "high", "critical")


@pytest.mark.parametrize("case", ALL_CASES, ids=[c.key for c in ALL_CASES])
def test_hunk_headers_add_up(case):
    header, *body = case.patch.rstrip("\n").split("\n")
    m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", header)
    assert m, header
    old_count = int(m.group(2) or 1)
    new_count = int(m.group(4) or 1)
    assert sum(1 for l in body if l[:1] in (" ", "-")) == old_count, f"{case.key}: old line count"
    assert sum(1 for l in body if l[:1] in (" ", "+")) == new_count, f"{case.key}: new line count"
    assert all(l[:1] in (" ", "+", "-") for l in body), f"{case.key}: every body line starts with space, plus or minus"


def test_key_case_is_redacted_before_the_model_sees_it():
    seen = redact_text(CASES_BY_KEY["hardcoded_key"].patch)
    assert "AKIA" not in seen and "[REDACTED:aws-access-key]" in seen


@pytest.mark.parametrize("name", ["prompt_corpus.py", "prompt_redteam.py"])
def test_no_token_shaped_literal_in_the_corpus_source(name):
    src = Path(__file__).with_name(name).read_text()
    assert not re.search(r"AKIA[0-9A-Z]{16}", src)
    assert not re.search(r"xox[abpr]-[0-9]{10}", src)


def test_red_team_cases_carry_their_attack_and_safe_behaviour():
    for case in REDTEAM_CASES:
        assert case.attack and case.expected_safe_behaviour and case.injection_line >= 0, case.key
        assert not case.clean and case.expect, case.key
