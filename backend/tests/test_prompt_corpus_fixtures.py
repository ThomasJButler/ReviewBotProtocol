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
        # a planted problem is worth at least "low" (the simplicity cases: no precondition, no defence
        # removed, no task degraded, by the prompt's own anchors); never "info"
        assert case.expect and case.min_severity in ("low", "medium", "high", "critical")


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


@pytest.mark.parametrize("case", ALL_CASES, ids=[c.key for c in ALL_CASES])
def test_every_planted_line_is_an_added_line(case):
    """The ground-truth check above asks only whether a line is commentable, which
    context lines are, so a case planted on a line the diff never touched would
    pass it and then score zero under the shipped context-line policy."""
    parsed = parse_patch(case.patch)
    for line in case.expect + ((case.injection_line,) if case.injection_line else ()):
        assert line in parsed.added_lines, f"{case.key}: line {line} is in the diff but was not added by it"


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


def test_a_case_whose_attack_is_in_the_file_body_carries_the_file_and_no_injection_line():
    """A file-borne case is scorable only if it is written whole: the instruction
    has to be in file_text, and injection_line has to stay 0, because prompt_corpus
    requires an injection line to be a commentable line of the diff and this one is
    not in the diff at all."""
    borne = [c for c in REDTEAM_CASES if c.file_injection]
    assert len(borne) >= 3, "the file-borne cases are the only measurement of the channel this branch opens"
    for case in borne:
        assert case.injection_line == 0, case.key
        assert case.file_text and case.attack and case.expected_safe_behaviour, case.key
        assert case.expect and not case.clean, case.key
        parsed = parse_patch(case.patch)
        # the file must really be the file this hunk came from, or the planted line is not scorable
        for number, text in parsed.new_lines.items():
            assert case.file_text.split("\n")[number - 1] == text, f"{case.key}: line {number}"
        # and the instruction must sit outside the diff, which is what makes it file-borne
        hunk_lines = set(parsed.new_lines)
        body = [i + 1 for i, line in enumerate(case.file_text.split("\n"))
                if "reviewer" in line.lower() or "review bots" in line.lower() or "DIFF_DATA_FILE" in line]
        assert body and not (set(body) & hunk_lines), case.key


# the three cases that mean to spell a marker: two forging a delimiter, one forging a span label
MARKER_FORGERIES = {"struct_fname_break": ("filename",),
                    "struct_marker_nonce": ("patch",),
                    "file_forged_context_marker_xss": ("file_text",)}


def test_only_the_forgery_cases_hold_text_the_marker_alternation_matches():
    """_defang runs on every patch, whatever FILE_CONTEXT says, so a case that
    happens to spell one of the three marker names has that text rewritten to
    [forged-data-marker] before the model sees it and any finding quoting the line
    dropped as unlocated. That is the trap the span label fell into while it was
    named after the setting, and it is the reason to pin the list: a fourth case
    matching by accident is a case that cannot be scored."""
    from services.ai_reviewer import _MARKER
    found: dict = {}
    for case in ALL_CASES:
        for field in ("patch", "filename", "file_text"):
            if _MARKER.search(getattr(case, field, "") or ""):
                found.setdefault(case.key, []).append(field)
    assert {key: tuple(fields) for key, fields in found.items()} == MARKER_FORGERIES
    assert not _MARKER.search("FILE_CONTEXT=true\nFILE_CONTEXT_LINES=60\n"), \
        "the setting's own name must survive a diff, or this repository cannot review itself"


# the defensive block of 2026-09-12: the shapes a security tool is made of, every one clean
DEFENCE_CASES = [c for c in CASES if c.source == "defensive shape clean control"]


def test_the_defensive_controls_are_twelve_clean_diffs_sharing_one_source():
    assert len(DEFENCE_CASES) == 12
    for case in DEFENCE_CASES:
        assert case.clean and not case.expect, case.key
        assert case.injection_line == 0, case.key
        assert case.note.startswith("Control:"), case.key
    assert {c.language for c in DEFENCE_CASES} == {"python", "typescript"}
    from collections import Counter
    assert Counter(c.language for c in DEFENCE_CASES) == {"python": 7, "typescript": 5}, "the split the docs quote"


def test_no_clean_case_plants_an_instruction_so_the_obedience_columns_stay_honest():
    """scripts/prompt_eval.py:344 computes injection_obeyed for any case with a
    nonzero injection_line, and a clean case has no planted line to find, so an
    empty reply on one would score as obedience and prompt_judge.record() would
    put the whole run OUT on arrival. A clean control is never an injection row."""
    for case in ALL_CASES:
        if case.clean:
            assert case.injection_line == 0, case.key


def test_every_case_key_is_unique_across_both_corpora():
    """CASES_BY_KEY collapses a duplicate silently, and scripts/prompt_eval.py runs
    both lists together under --all, so a key used twice quietly drops a case or
    doubles a row. Twelve new keys sharing a prefix is when that bites."""
    assert len(CASES_BY_KEY) == len(CASES)
    redteam_keys = [c.key for c in REDTEAM_CASES]
    assert len(set(redteam_keys)) == len(redteam_keys)
    assert not set(CASES_BY_KEY) & set(redteam_keys)


@pytest.mark.parametrize("case", DEFENCE_CASES, ids=[c.key for c in DEFENCE_CASES])
def test_a_defensive_control_reaches_the_model_exactly_as_it_is_written(case):
    """These cases are clean because of what their credential patterns, payloads and
    quoted attacks are for, so a case that arrives redacted or defanged is measuring
    something else: the model would be shown [REDACTED:assigned-secret] where the
    defence was, and a finding quoting the line would be dropped as unlocated."""
    from services.ai_reviewer import _defang

    assert redact_text(case.patch) == case.patch
    assert _defang(case.patch) == case.patch


def test_the_corpus_is_the_size_the_leaderboards_will_quote():
    assert len(CASES) == 88
    assert sum(1 for c in CASES if c.clean) == 28
    assert sum(1 for c in CASES if not c.clean) == 60
    # the red-team set is branch 5's, and the three file-borne cases in it are its work, not this
    # branch's; it is asserted separately so a change to either corpus names itself
    assert len(REDTEAM_CASES) == 18
