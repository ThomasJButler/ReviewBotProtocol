"""The precision harness: the fixed set, the fingerprint, the ledger, the
sheet, the merge, the score and the replay.

The git-dependent tests here regenerate the diff of a real range and are
skipped when the checkout is shallow (CI clones at depth 1) or git is missing;
the database-dependent ones are skipped when backend/reviews.db is absent,
since *.db is gitignored. Everything else runs anywhere: hand-built records,
hand-built ledgers and literal diff strings, with the fake model and the egress
guard, so no test needs Ollama, a network or the machine's own git history.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import precision as P  # noqa: E402

from services.diff import locate_evidence, parse_patch  # noqa: E402
from services.review_runner import prepare_files, select_files  # noqa: E402
from tests.fakes import RecordingChatModel  # noqa: E402

SET = json.loads(P.PR_SET.read_text(encoding="utf-8"))
NUMBERS = [r["number"] for r in SET["pull_requests"]]
DB = P.BACKEND / "reviews.db"


def _shallow_or_no_git() -> bool:
    try:
        done = subprocess.run(["git", "-C", str(P.REPO), "rev-parse", "--is-shallow-repository"],
                              capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return True
    return done.returncode != 0 or done.stdout.strip() == "true"


needs_history = pytest.mark.skipif(_shallow_or_no_git(),
                                  reason="the checkout is shallow or git is missing, so the v1.2 commits are not here")
needs_database = pytest.mark.skipif(not DB.is_file(), reason="backend/reviews.db is gitignored and not on this machine")

# One diff, two files, written out rather than fetched, so the tests that drive the
# pipeline need neither git nor a model. New-file lines of handler.py: 1 context,
# 2 and 3 added, 4 context, 5 and 6 added.
DIFF = (
    "diff --git a/app/handler.py b/app/handler.py\n"
    "index 1111111..2222222 100644\n"
    "--- a/app/handler.py\n"
    "+++ b/app/handler.py\n"
    "@@ -1,4 +1,6 @@\n"
    " import os\n"
    "+import sqlite3\n"
    "+\n"
    " def handle(request):\n"
    "-    return None\n"
    "+    query = \"select * from users where name = '\" + request.name + \"'\"\n"
    "+    return sqlite3.connect('app.db').execute(query)\n"
    "diff --git a/app/util.js b/app/util.js\n"
    "index 3333333..4444444 100644\n"
    "--- a/app/util.js\n"
    "+++ b/app/util.js\n"
    "@@ -1,3 +1,4 @@\n"
    " export function render(name) {\n"
    "-  return name;\n"
    "+  document.body.innerHTML = name;\n"
    "+  return name;\n"
    " }\n"
)
QUERY_LINE = "query = \"select * from users where name = '\" + request.name + \"'\""
ONE_FINDING = json.dumps({"findings": [
    {"category": "security", "severity": "high", "title": "SQL built by string concatenation",
     "line": 5, "evidence": QUERY_LINE, "recommendation": "Use a parameterised query.", "confidence": 0.9}],
    "summary": "One problem."})
ENTRY = {"number": 24, "title": "A pull request", "base_sha": "a" * 40, "head_sha": "b" * 40,
         "files": 2, "selected_at_recorded_settings": 2}


def _settings(**kwargs):
    return P.settings_for(model="fake-model", **kwargs)


def _round(diff: str = DIFF, reply: str = ONE_FINDING, entry=None, pr_number=None):
    """One pull request through the real pipeline with a fake model, returning
    the record the harness would write. Synchronous, and its own event loop, so
    every test below can call P.main the way a person does."""
    settings = _settings()
    llm = RecordingChatModel(response=reply)
    recorder = P.Recorder()
    llm.callbacks = [recorder]
    reviewer = P.FileReviewer(llm, settings)
    row = dict(entry or ENTRY)
    if pr_number is not None:
        row["number"] = pr_number
    record = asyncio.run(P.review_pull_request(row, diff, reviewer, recorder, settings))
    record["tag"], record["repository"] = "round1", SET["repository"]
    return record


def _write(tmp_path: Path, tag: str, records) -> Path:
    runs = tmp_path / "runs"
    runs.mkdir(exist_ok=True)
    for record in records:
        P.write_record(runs, tag, SET["repository"], record)
    return runs


def _judgement(finding, pull_requests=(24,), verdicts=("real", "real"), reasons=("wrong_about_code", "wrong_about_code")):
    judges = []
    for name, verdict, reason in zip(("judge-a", "judge-b"), verdicts, reasons):
        judges.append({"judge": name, "verdict": verdict,
                       "reason_category": reason if verdict == "not_real" else "",
                       "reason": "because of the code", "date": "2026-09-12"})
    return {"fingerprint": finding["fingerprint"], "pull_requests": list(pull_requests), "path": finding["path"],
            "line": finding["line"], "category": finding["category"], "title": finding["title"],
            "evidence": finding["evidence"], "first_seen": "round1", "judges": judges}


def _ledger(tmp_path: Path, monkeypatch, entries=()) -> Path:
    path = tmp_path / "judgements.json"
    path.write_text(json.dumps({"version": 1, "judgements": list(entries)}, indent=1), encoding="utf-8")
    monkeypatch.setattr(P, "LEDGER", path)
    return path


# ---------------------------------------------------------------- the fixed set


def test_the_fixed_set_names_the_eleven_v1_2_pull_requests_with_a_base_and_a_head():
    assert SET["release"] == "v1.2"
    assert NUMBERS == list(range(23, 34))
    for row in SET["pull_requests"]:
        assert len(row["base_sha"]) == 40 and len(row["head_sha"]) == 40, row
        assert set(row["base_sha"]) <= set("0123456789abcdef"), row
        assert row["title"] and row["files"] > 0
        assert 0 <= row["selected_at_recorded_settings"] <= row["files"]
    assert SET["database"]["repository"] == "ThomasJButler/ReviewBot-Protocol", \
        "the database still holds the pre-rename name, and a query has to use it"
    assert SET["repository"] == "ThomasJButler/ReviewBotProtocol"


def test_each_base_is_the_previous_pull_requests_head_so_the_stack_is_linear():
    rows = SET["pull_requests"]
    for earlier, later in zip(rows, rows[1:]):
        assert later["base_sha"] == earlier["head_sha"], f"pr {later['number']} does not follow pr {earlier['number']}"


@needs_history
def test_the_shas_in_the_fixed_set_exist_in_git_unless_the_checkout_is_shallow():
    for row in SET["pull_requests"]:
        for sha in (row["base_sha"], row["head_sha"]):
            kind = P.git("cat-file", "-t", sha).strip()
            assert kind == "commit", f"{sha} is a {kind}, not a commit"


@needs_database
def test_every_pull_request_in_the_set_carries_the_head_sha_the_database_recorded():
    import sqlite3

    conn = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True)
    try:
        recorded = dict(conn.execute(
            "select pr_number, head_sha from reviews where repository = ? and pr_number between 23 and 33 "
            "and status = 'completed'", (SET["database"]["repository"],)))
    finally:
        conn.close()
    assert set(recorded) == set(NUMBERS)
    for row in SET["pull_requests"]:
        assert row["head_sha"] == recorded[row["number"]], f"pr {row['number']} names a head the database does not"


@needs_history
def test_the_range_of_each_pull_request_splits_into_the_file_count_the_set_records():
    for row in SET["pull_requests"]:
        files = P.split_git_diff(P.diff_text(row["base_sha"], row["head_sha"]))
        named = [n for n in P.git("diff", "--name-only", f"{row['base_sha']}...{row['head_sha']}").split("\n") if n]
        assert len(files) == row["files"] == len(named), f"pr {row['number']}"


@needs_history
def test_selecting_from_the_regenerated_diff_reproduces_the_file_count_the_night_reviewed():
    settings = _settings()
    assert settings.MAX_FILES_PER_REVIEW == 25, "the recorded round ran at 50 and the largest eligible set is 16"
    for row in SET["pull_requests"]:
        selected, _ = select_files(P.split_git_diff(P.diff_text(row["base_sha"], row["head_sha"])), settings)
        assert len(selected) == row["selected_at_recorded_settings"], f"pr {row['number']}"


@needs_history
def test_the_split_addition_counts_match_git_numstat():
    for row in SET["pull_requests"]:
        numstat = {}
        for line in P.git("diff", "--numstat", f"{row['base_sha']}...{row['head_sha']}").split("\n"):
            if line:
                added, _, path = line.split("\t")
                numstat[path] = added
        for f in P.split_git_diff(P.diff_text(row["base_sha"], row["head_sha"])):
            if numstat.get(f["filename"], "-") != "-":
                assert f["additions"] == int(numstat[f["filename"]]), f"pr {row['number']} {f['filename']}"


@needs_history
@needs_database
def test_every_stored_finding_relocates_to_the_line_the_database_recorded():
    """The proof that a regenerated diff is the diff the model was shown: every
    one of the stored findings still locates on the line the night recorded."""
    stored, _ = P.read_database(str(DB), SET["database"]["repository"])
    settings = _settings()
    checked = 0
    for row in SET["pull_requests"]:
        findings = stored.get(row["number"], [])
        if not findings:
            continue
        selected, _ = select_files(P.split_git_diff(P.diff_text(row["base_sha"], row["head_sha"])), settings)
        prepared, _ = prepare_files(selected)
        patches = {f["filename"]: f["patch"] for f in prepared}
        for f in findings:
            assert f["path"] in patches, f"pr {row['number']}: {f['path']} was not selected"
            located = locate_evidence(parse_patch(patches[f["path"]]), f["line"], f["evidence"])
            assert located == f["line"], f"pr {row['number']} {f['path']}:{f['line']} relocated to {located}"
            checked += 1
    assert checked == 22, f"the 2026-09-07 round stored 22 findings, not {checked}"


# ---------------------------------------------------------------- the ledger


def test_the_ledger_in_the_repository_passes_its_own_validator():
    assert P.validate_ledger(P.load_ledger(), NUMBERS) == []


def test_every_ledger_entry_names_a_pull_request_the_fixed_set_holds():
    finding = {"fingerprint": "", "path": "a.py", "line": 1, "category": "quality", "title": "A title",
               "evidence": "x = 1"}
    finding["fingerprint"] = P.fingerprint(finding["path"], finding["title"], finding["evidence"])
    good = {"version": 1, "judgements": [_judgement(finding, pull_requests=(24,))]}
    assert P.validate_ledger(good, NUMBERS) == []
    bad = {"version": 1, "judgements": [_judgement(finding, pull_requests=(99,))]}
    assert any("99" in complaint for complaint in P.validate_ledger(bad, NUMBERS))


def test_a_ledger_fingerprint_that_does_not_match_its_own_path_title_and_evidence_is_refused():
    entry = _judgement({"fingerprint": "0" * 12, "path": "a.py", "line": 1, "category": "quality",
                        "title": "A title", "evidence": "x = 1"})
    complaints = P.validate_ledger({"version": 1, "judgements": [entry]}, NUMBERS)
    assert any("does not match its own path, title and evidence" in c for c in complaints)


def test_a_verdict_of_not_real_without_a_reason_category_is_refused():
    finding = {"path": "a.py", "line": 1, "category": "quality", "title": "A title", "evidence": "x = 1"}
    finding["fingerprint"] = P.fingerprint(finding["path"], finding["title"], finding["evidence"])
    entry = _judgement(finding, verdicts=("not_real", "not_real"))
    entry["judges"][0]["reason_category"] = ""
    complaints = P.validate_ledger({"version": 1, "judgements": [entry]}, NUMBERS)
    assert any("needs a reason_category" in c for c in complaints)


def test_a_reason_category_outside_the_six_is_refused():
    finding = {"path": "a.py", "line": 1, "category": "quality", "title": "A title", "evidence": "x = 1"}
    finding["fingerprint"] = P.fingerprint(finding["path"], finding["title"], finding["evidence"])
    entry = _judgement(finding, verdicts=("not_real", "not_real"), reasons=("did_not_like_it", "other"))
    complaints = P.validate_ledger({"version": 1, "judgements": [entry]}, NUMBERS)
    assert any("did_not_like_it" in c for c in complaints)
    assert P.REASON_CATEGORIES == ("wrong_about_code", "style_preference", "untouched_line", "defence_as_attack",
                                   "instruction_title", "other")


def test_two_verdicts_from_the_same_judge_are_not_two_judges():
    finding = {"path": "a.py", "line": 1, "category": "quality", "title": "A title", "evidence": "x = 1"}
    finding["fingerprint"] = P.fingerprint(finding["path"], finding["title"], finding["evidence"])
    entry = _judgement(finding)
    entry["judges"][1]["judge"] = entry["judges"][0]["judge"]
    complaints = P.validate_ledger({"version": 1, "judgements": [entry]}, NUMBERS)
    assert any("which is one judge and not two" in c for c in complaints)


# ---------------------------------------------------------------- the fingerprint


def test_the_fingerprint_ignores_title_case_whitespace_and_trailing_punctuation():
    one = P.fingerprint("a.py", "SQL built by concatenation", "x = 1")
    assert one == P.fingerprint("a.py", "  sql  built   by concatenation.  ", "x = 1")
    assert one == P.fingerprint("a.py", "`SQL built by concatenation`", "x = 1")
    assert one != P.fingerprint("b.py", "SQL built by concatenation", "x = 1")


def test_the_fingerprint_ignores_a_quoted_diff_marker_and_the_kind_inside_a_redaction_marker():
    one = P.fingerprint("a.py", "A title", "token = [REDACTED:aws-key]")
    assert one == P.fingerprint("a.py", "A title", "+ token = [REDACTED:github-token]")
    assert one == P.fingerprint("a.py", "A title", '  token   =   [REDACTED:other]  ')
    assert P.fingerprint("a.py", "A title", "X = 1") != P.fingerprint("a.py", "A title", "x = 1"), \
        "case in the evidence is the code, so it is kept"


def test_two_findings_with_the_same_title_on_one_file_get_different_fingerprints_from_their_evidence():
    path, title = "backend/tests/test_settings_reference.py", "YAGNI: Remove redundant assertion message text"
    assert P.fingerprint(path, title, "assert one, 'the first message'") != \
        P.fingerprint(path, title, "assert two, 'the second message'")


def test_the_same_finding_on_a_later_pull_request_keeps_one_fingerprint_and_gains_a_pull_request(tmp_path, monkeypatch):
    first = _round(pr_number=24)
    again = _round(pr_number=29)
    assert first["findings"][0]["fingerprint"] == again["findings"][0]["fingerprint"], \
        "the pull request number is deliberately not in the fingerprint"
    ledger = _ledger(tmp_path, monkeypatch, [_judgement(first["findings"][0], pull_requests=(24,))])
    filled = _fill(tmp_path, "round1", again, "judge-a", "real"), _fill(tmp_path, "round1", again, "judge-b", "real")
    assert P.main(["merge", str(filled[0]), str(filled[1]), "--skip-existing"]) == 0
    entry = json.loads(ledger.read_text(encoding="utf-8"))["judgements"][0]
    assert entry["pull_requests"] == [24, 29]


def _fill(tmp_path: Path, tag: str, record, judge: str, verdict: str, reason_category: str = "",
          only=None) -> Path:
    """A filled skeleton, as a judge hands it back."""
    rows = [(record, f, [record["pr"]]) for f in record["findings"] if only is None or f["fingerprint"] in only]
    doc = P.skeleton(tag, rows)
    doc["judge"], doc["date"] = judge, "2026-09-12"
    for v in doc["verdicts"]:
        v["verdict"] = verdict
        v["reason_category"] = reason_category if verdict == "not_real" else ""
        v["reason"] = "one line of reason"
    path = tmp_path / f"{tag}-{judge}.json"
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


# ---------------------------------------------------------------- score


def test_precision_is_the_share_of_judged_findings_both_judges_called_real(tmp_path, monkeypatch, capsys):
    real = _round(pr_number=24)
    not_real = _round(pr_number=29, diff=_second_diff(), reply=_second_reply())
    _ledger(tmp_path, monkeypatch, [_judgement(real["findings"][0]),
                                    _judgement(not_real["findings"][0], pull_requests=(29,),
                                               verdicts=("not_real", "not_real"),
                                               reasons=("style_preference", "style_preference"))])
    runs = _write(tmp_path, "round1", [real, not_real])
    assert P.main(["score", str(runs), "round1"]) == 0
    out = capsys.readouterr().out
    assert "judged        2 of 2" in out
    assert "real          1 (both judges)" in out
    assert "precision     0.50 (1/2 judged)" in out


def _second_diff() -> str:
    return (
        "diff --git a/app/other.py b/app/other.py\n"
        "index 5555555..6666666 100644\n"
        "--- a/app/other.py\n"
        "+++ b/app/other.py\n"
        "@@ -1,2 +1,3 @@\n"
        " import json\n"
        "+PAGE_SIZE = 50  # the page size the dashboard asks for\n"
        " def load():\n"
    )


def _second_reply() -> str:
    return json.dumps({"findings": [
        {"category": "quality", "severity": "low", "title": "Magic number in a constant",
         "line": 2, "evidence": "PAGE_SIZE = 50  # the page size the dashboard asks for",
         "recommendation": "Name the page size in the settings instead.", "confidence": 0.8}],
        "summary": "One note."})


def test_a_finding_the_two_judges_disagree_about_is_counted_as_disputed_and_not_as_real(tmp_path, monkeypatch, capsys):
    record = _round()
    _ledger(tmp_path, monkeypatch, [_judgement(record["findings"][0], verdicts=("real", "not_real"),
                                               reasons=("", "style_preference"))])
    runs = _write(tmp_path, "round1", [record])
    assert P.main(["score", str(runs), "round1"]) == 0
    out = capsys.readouterr().out
    assert "disputed      1" in out
    assert "real          0 (both judges)" in out
    assert "precision     0.00 (0/1 judged)" in out


def test_an_unjudged_finding_blocks_the_number_names_itself_and_exits_non_zero(tmp_path, monkeypatch, capsys):
    record = _round()
    _ledger(tmp_path, monkeypatch)
    runs = _write(tmp_path, "round1", [record])
    assert P.main(["score", str(runs), "round1"]) == 2
    captured = capsys.readouterr()
    assert record["findings"][0]["fingerprint"] in captured.err
    assert "nobody has judged" in captured.err
    assert "precision     partial (0 of 1 judged)" in captured.out


def test_the_reason_breakdown_counts_one_vote_per_judge_per_finding(tmp_path, monkeypatch, capsys):
    record = _round()
    _ledger(tmp_path, monkeypatch, [_judgement(record["findings"][0], verdicts=("not_real", "not_real"),
                                               reasons=("wrong_about_code", "untouched_line"))])
    runs = _write(tmp_path, "round1", [record])
    P.main(["score", str(runs), "round1"])
    out = capsys.readouterr().out
    assert "wrong_about_code   1" in out
    assert "untouched_line     1" in out, "one finding can carry two different categories, one per judge"


def test_the_per_pull_request_table_counts_a_recurring_finding_under_both_pull_requests(tmp_path, monkeypatch, capsys):
    first = _round(pr_number=24)
    again = _round(pr_number=29)
    _ledger(tmp_path, monkeypatch, [_judgement(first["findings"][0], pull_requests=(24, 29))])
    runs = _write(tmp_path, "round1", [first, again])
    assert P.main(["score", str(runs), "round1"]) == 0
    out = capsys.readouterr().out
    assert "findings      2 occurrences" in out
    assert "distinct      1 fingerprints" in out
    rows = [line for line in out.splitlines() if line.strip().startswith(("24 ", "29 "))]
    assert len(rows) == 2 and all(" 1 " in row for row in rows)


# ---------------------------------------------------------------- sheet


def test_the_sheet_lists_only_the_unjudged_findings_with_the_diff_lines_around_them_and_marks_the_added_ones(
        tmp_path, monkeypatch, capsys):
    judged = _round(pr_number=24)
    fresh = _round(pr_number=29, diff=_second_diff(), reply=_second_reply())
    _ledger(tmp_path, monkeypatch, [_judgement(judged["findings"][0])])
    runs = _write(tmp_path, "round1", [judged, fresh])
    assert P.main(["sheet", str(runs), "round1"]) == 0
    out = capsys.readouterr().out
    assert "1 finding nobody has judged" in out
    assert judged["findings"][0]["fingerprint"] not in out
    assert fresh["findings"][0]["fingerprint"] in out
    assert "+     2  PAGE_SIZE = 50" in out and "<-- the finding" in out
    assert "      1  import json" in out, "a context line is listed without the added marker"


def test_the_sheet_names_an_already_judged_finding_with_the_same_evidence_as_a_possible_refingerprint(
        tmp_path, monkeypatch, capsys):
    record = _round()
    finding = record["findings"][0]
    retitled = dict(finding, title="The reviewer's own sentence, retitled")
    retitled["fingerprint"] = P.fingerprint(retitled["path"], retitled["title"], retitled["evidence"])
    _ledger(tmp_path, monkeypatch, [_judgement(retitled)])
    runs = _write(tmp_path, "round1", [record])
    P.main(["sheet", str(runs), "round1"])
    out = capsys.readouterr().out
    assert "re-fingerprinted" in out and retitled["fingerprint"] in out


def test_the_sheet_writes_the_table_and_the_skeleton_in_one_pass(tmp_path, monkeypatch, capsys):
    record = _round()
    _ledger(tmp_path, monkeypatch)
    runs = _write(tmp_path, "round1", [record])
    out_dir = tmp_path / "sheets"
    assert P.main(["sheet", str(runs), "round1", "--out", str(out_dir)]) == 0
    sheet = (out_dir / "round1-sheet.md").read_text(encoding="utf-8")
    skeleton = json.loads((out_dir / "round1-skeleton.json").read_text(encoding="utf-8"))
    assert record["findings"][0]["fingerprint"] in sheet
    assert skeleton["run"] == "round1" and skeleton["judge"] == "" and skeleton["date"] == ""
    assert [v["fingerprint"] for v in skeleton["verdicts"]] == [record["findings"][0]["fingerprint"]]
    assert all(v["verdict"] == "" and v["reason"] == "" for v in skeleton["verdicts"])
    assert "1 unjudged fingerprints" in capsys.readouterr().out


# ---------------------------------------------------------------- merge


def test_a_filled_sheet_skeleton_merges_into_the_ledger_and_then_scores(tmp_path, monkeypatch, capsys):
    record = _round()
    ledger = _ledger(tmp_path, monkeypatch)
    runs = _write(tmp_path, "round1", [record])
    a = _fill(tmp_path, "round1", record, "judge-a", "not_real", "style_preference")
    b = _fill(tmp_path, "round1", record, "judge-b", "not_real", "wrong_about_code")
    assert P.main(["merge", str(a), str(b)]) == 0
    data = json.loads(ledger.read_text(encoding="utf-8"))
    assert P.validate_ledger(data, NUMBERS) == []
    assert [j["judge"] for j in data["judgements"][0]["judges"]] == ["judge-a", "judge-b"]
    assert data["judgements"][0]["first_seen"] == "round1"
    capsys.readouterr()
    assert P.main(["score", str(runs), "round1"]) == 0
    out = capsys.readouterr().out
    assert "judged        1 of 1" in out and "precision     0.00 (0/1 judged)" in out


def test_merge_refuses_a_fingerprint_the_ledger_already_holds(tmp_path, monkeypatch, capsys):
    record = _round()
    _ledger(tmp_path, monkeypatch, [_judgement(record["findings"][0])])
    a = _fill(tmp_path, "round1", record, "judge-c", "real")
    b = _fill(tmp_path, "round1", record, "judge-d", "real")
    assert P.main(["merge", str(a), str(b)]) == 2
    assert "already in the ledger" in capsys.readouterr().err


def test_merge_refuses_two_verdicts_from_one_judge_and_a_verdict_with_no_reason(tmp_path, monkeypatch, capsys):
    record = _round()
    _ledger(tmp_path, monkeypatch)
    a = _fill(tmp_path, "round1", record, "judge-a", "real")
    assert P.main(["merge", str(a), str(a)]) == 2
    assert "independent judgements" in capsys.readouterr().err
    b = _fill(tmp_path, "round1", record, "judge-b", "real")
    doc = json.loads(b.read_text(encoding="utf-8"))
    doc["verdicts"][0]["reason"] = "  "
    b.write_text(json.dumps(doc), encoding="utf-8")
    assert P.main(["merge", str(a), str(b)]) == 2
    assert "has no reason" in capsys.readouterr().err


# ---------------------------------------------------------------- run


def test_a_run_over_a_literal_diff_writes_one_record_per_pull_request_with_every_raw_reply_and_dials_nothing_but_loopback(
        tmp_path, no_egress):
    settings = P.settings_for(model="fake-model", cross_model="fake-cross")
    llm = RecordingChatModel(response=ONE_FINDING)
    cross = RecordingChatModel(response=json.dumps({"verdicts": [{"index": 0, "verdict": "real", "severity": "high",
                                                                 "reason": "the concatenation is there", "confidence": 0.9}],
                                                    "additions": [], "summary_note": "agreed"}))
    recorder = P.Recorder()
    llm.callbacks = [recorder]
    cross.callbacks = [recorder]
    reviewer = P.FileReviewer(llm, settings, cross_llm=cross)
    record = asyncio.run(P.review_pull_request(ENTRY, DIFF, reviewer, recorder, settings))
    assert reviewer.cross_inline is False, "the two phases are this loop's, not review_file's"
    assert record["split"] == 2 and len(record["files"]) == 2
    assert [f["filename"] for f in record["files"]] == ["app/handler.py", "app/util.js"]
    assert all(f["model_texts"] for f in record["files"]), "every raw reply is kept, reviewer first"
    assert record["files"][0]["model_texts"][0] == ONE_FINDING
    assert len(record["files"][0]["model_texts"]) == 2, "the cross-examiner's reply is the second"
    assert record["findings"][0]["fingerprint"] == P.fingerprint("app/handler.py", "SQL built by string concatenation",
                                                                QUERY_LINE)
    assert record["findings"][0]["cross_verdict"] == "real"
    out = tmp_path / "records"
    out.mkdir()
    path = P.write_record(out, "round1", SET["repository"], record)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "round1-pr24.json"
    assert written["replayable"] is True and written["tag"] == "round1"
    assert written["settings"]["min_finding_confidence"] == settings.MIN_FINDING_CONFIDENCE


def test_a_record_counts_the_drops_by_the_postprocess_rules(tmp_path):
    """One reply carrying one of each: a real finding, the same finding again, a
    finding under the confidence floor, a tag-only title, praise filed as a
    finding, and a quote that is not in the diff."""
    good = {"category": "security", "severity": "high", "title": "SQL built by string concatenation", "line": 5,
            "evidence": QUERY_LINE, "recommendation": "Use a parameterised query.", "confidence": 0.9}
    reply = json.dumps({"findings": [
        good, dict(good),
        dict(good, title="Timid finding", confidence=0.1),
        dict(good, title="shrink"),
        dict(good, title="The query is fine", recommendation="No change is needed."),
        dict(good, title="Invented line", line=99, evidence="nothing in this diff says this at all"),
    ], "summary": "Six."})
    record = _round(reply=reply)
    handler = record["files"][0]
    assert handler["raw"] == 6
    assert handler["drops"] == {"confidence": 1, "tag_title": 1, "praise": 1, "unlocated": 1, "duplicate": 1,
                                "outside_diff": 0, "context_line": 0, "context_line_downgraded": 0}
    assert len([f for f in record["findings"] if f["path"] == "app/handler.py"]) == 1


def test_every_postprocess_drop_rule_has_a_counter_in_the_record():
    """The counters are read off the postprocess rather than remembered: a rule
    added there with no counter here would leave a round unable to say why a
    finding vanished."""
    import inspect
    import re as _re

    from services import ai_reviewer

    named = set(_re.findall(r'dropped\(f, "(\w+)"\)', inspect.getsource(ai_reviewer.postprocess)))
    named |= set(_re.findall(r'return "(\w+)"', inspect.getsource(ai_reviewer.drop_rule)))
    assert named == set(P.DROP_RULES), f"postprocess names {sorted(named)}, the record counts {sorted(P.DROP_RULES)}"


def test_a_run_refuses_to_write_its_records_inside_the_repository(capsys):
    assert P.main(["run", "--out", str(P.BACKEND / "precision-runs"), "--tag", "round1"]) == 2
    assert "inside the repository working tree" in capsys.readouterr().err
    with pytest.raises(P.CannotRun):
        P.refuse_out_inside_repo(str(P.REPO))


def test_a_cloud_model_tag_is_refused_by_the_settings_guard_for_either_model():
    with pytest.raises(P.CannotRun) as reviewer:
        P.settings_for(model="qwen3.5:9b-cloud")
    assert "local-only guard" in str(reviewer.value)
    with pytest.raises(P.CannotRun) as cross:
        P.settings_for(model="qwen3.5:9b", cross_model="gemma4:12b-cloud")
    assert "CROSS_EXAMINE_MODEL" in str(cross.value)


def test_the_database_round_is_built_from_the_stored_findings_with_no_model_and_is_marked_unreplayable(tmp_path):
    """The round 0 path: one read-only immutable query, patches regenerated for
    context, no model and nothing replayable. The database here is built with
    the columns the harness's own query names."""
    import sqlite3

    path = tmp_path / "reviews.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "create table reviews (id text, repository text, pr_number int, head_sha text, status text, model text,"
        " cross_model text, started_at text, duration_seconds real, created_at text);"
        "create table findings (review_id text, path text, line int, category text, severity text, title text,"
        " evidence text, recommendation text, confidence real, source_model text, cross_verdict text,"
        " cross_reason text);")
    conn.execute("insert into reviews values ('r1', 'Owner/Name', 24, 'b', 'completed', 'qwen3.5:9b', 'gemma4:12b',"
                 " '2026-09-07 22:59:30', 672.4, '2026-09-07 22:48:11')")
    conn.execute("insert into findings values ('r1', 'app/handler.py', 5, 'security', 'high',"
                 " 'SQL built by string concatenation', ?, 'Use a parameterised query.', 0.9, 'qwen3.5:9b', 'real', '')",
                 (QUERY_LINE,))
    conn.commit()
    conn.close()
    stored, meta = P.read_database(str(path), "Owner/Name")
    assert list(stored) == [24] and meta[24]["model"] == "qwen3.5:9b"
    assert stored[24][0]["fingerprint"] == P.fingerprint("app/handler.py", "SQL built by string concatenation",
                                                        QUERY_LINE)
    record = P.database_record(ENTRY, DIFF, _settings(), stored[24], meta[24])
    assert record["replayable"] is False
    assert record["model"] == "qwen3.5:9b" and record["cross_model"] == "gemma4:12b"
    assert record["seconds"] == 672.4 and record["started_at"] == "2026-09-07 22:59:30"
    assert all(f["model_texts"] == [] for f in record["files"])
    assert len(record["findings"]) == 1
    assert record["files"][0]["patch"].startswith("@@"), "the patch is regenerated so the sheet has context"
    assert P.main(["replay", str(_write(tmp_path, "round0", [record])), "round0", "--out", str(tmp_path / "again"),
                   "--tag-out", "round0-after"]) == 2


# ---------------------------------------------------------------- replay


def test_a_replay_carries_the_judgements_by_fingerprint_and_prints_the_number_before_and_after(
        tmp_path, monkeypatch, capsys):
    record = _round()
    _ledger(tmp_path, monkeypatch, [_judgement(record["findings"][0])])
    runs = _write(tmp_path, "round1", [record])
    out = tmp_path / "after"
    assert P.main(["replay", str(runs), "round1", "--out", str(out), "--tag-out", "round1-after"]) == 0
    printed = capsys.readouterr().out
    assert "no model loaded" in printed
    assert "findings             1       1" in printed
    assert "precision         1.00    1.00" in printed
    assert "already judged" in printed
    again = json.loads((out / "round1-after-pr24.json").read_text(encoding="utf-8"))
    assert again["findings"][0]["fingerprint"] == record["findings"][0]["fingerprint"]
    assert again["replayed_from"]["tag"] == "round1"


def test_a_replay_skips_a_file_that_recorded_no_reply_and_carries_its_error_into_both_counts(
        tmp_path, monkeypatch, capsys):
    record = _round()
    record["files"].append({"filename": "app/broken.py", "language": "python", "status": "modified", "additions": 1,
                            "patch": "@@ -1,1 +1,2 @@\n import os\n+x = 1\n", "model_texts": [], "raw": 0,
                            "drops": {rule: 0 for rule in P.DROP_RULES}, "prompt_tokens": 0, "output_tokens": 0,
                            "seconds": 0.0, "parse_ok": False, "error": "ReadTimeout"})
    _ledger(tmp_path, monkeypatch, [_judgement(record["findings"][0])])
    runs = _write(tmp_path, "round1", [record])
    out = tmp_path / "after"
    assert P.main(["replay", str(runs), "round1", "--out", str(out), "--tag-out", "round1-after"]) == 0
    printed = capsys.readouterr().out
    assert "1 file(s) recorded no reply and were carried, not re-reviewed" in printed
    again = json.loads((out / "round1-after-pr24.json").read_text(encoding="utf-8"))
    assert [e["path"] for e in again["errored"]] == ["app/broken.py"]
    assert [e["reason"] for e in again["errored"]] == ["ReadTimeout"]
    assert "findings             1       1" in printed, "the denominator is the same on both lines"


def test_a_replay_that_produces_a_finding_nobody_has_judged_bounds_the_number_and_exits_non_zero(
        tmp_path, monkeypatch, capsys):
    """Two judged findings, one real and one not, and a third the replay brings
    out: the bound straddles the number before, so the round cannot be read
    until the new finding is judged."""
    extra = {"category": "quality", "severity": "low", "title": "An import that is not used", "line": 2,
             "evidence": "import sqlite3", "recommendation": "Delete the import.", "confidence": 0.8}
    second = {"category": "quality", "severity": "low", "title": "Innerhtml assignment", "line": 2,
              "evidence": "document.body.innerHTML = name;", "recommendation": "Set textContent instead.",
              "confidence": 0.8}
    before_reply = json.dumps({"findings": [json.loads(ONE_FINDING)["findings"][0]], "summary": "One."})
    after_reply = json.dumps({"findings": [json.loads(ONE_FINDING)["findings"][0], extra], "summary": "Two."})
    record = _round(reply=before_reply)
    handler = next(f for f in record["files"] if f["filename"] == "app/handler.py")
    util = next(f for f in record["files"] if f["filename"] == "app/util.js")
    util_record = _round(diff=DIFF, reply=json.dumps({"findings": [second], "summary": "One."}))
    record["findings"] = [record["findings"][0], next(f for f in util_record["findings"] if f["path"] == "app/util.js")]
    handler["model_texts"] = [after_reply]
    util["model_texts"] = [json.dumps({"findings": [second], "summary": "One."})]
    _ledger(tmp_path, monkeypatch, [
        _judgement(record["findings"][0]),
        _judgement(record["findings"][1], verdicts=("not_real", "not_real"),
                   reasons=("style_preference", "style_preference"))])
    runs = _write(tmp_path, "round1", [record])
    assert P.main(["replay", str(runs), "round1", "--out", str(tmp_path / "after"), "--tag-out", "round1-after"]) == 2
    captured = capsys.readouterr()
    assert "precision after is between 0.33 and 0.67, against 0.50 before" in captured.out
    assert "An import that is not used" in captured.out
    assert "have to be judged" in captured.err


def test_a_replay_refuses_a_record_that_holds_no_model_replies(tmp_path, capsys):
    record = _round()
    record["replayable"] = False
    runs = _write(tmp_path, "round0", [record])
    assert P.main(["replay", str(runs), "round0", "--out", str(tmp_path / "after"), "--tag-out", "after"]) == 2
    assert "replayable false" in capsys.readouterr().err


# ---------------------------------------------------------------- the drops and the provenance


def test_two_instruction_titled_findings_that_retitle_the_same_way_are_one_duplicate(tmp_path):
    """The record counts the drops through the postprocess itself. Both titles
    here are the prompt's own sentence, so the postprocess replaces each with
    the first sentence of the recommendation, and the two findings then collide
    on one line under one title: a drop a copy of the loop could not see,
    because it deduped on the title the model typed."""
    instruction = "yagni, delete, stdlib, native or shrink, then what to remove"
    one = {"category": "quality", "severity": "low", "title": instruction, "line": 5, "evidence": QUERY_LINE,
           "recommendation": "Use a parameterised query. The concatenation is the problem.", "confidence": 0.9}
    two = dict(one, title=instruction + ", never the tag alone")
    record = _round(reply=json.dumps({"findings": [one, two], "summary": "Two."}))
    handler = next(f for f in record["files"] if f["filename"] == "app/handler.py")
    assert handler["raw"] == 2
    assert handler["drops"]["duplicate"] == 1 and sum(handler["drops"].values()) == 1
    kept = [f for f in record["findings"] if f["path"] == "app/handler.py"]
    assert [f["title"] for f in kept] == ["Use a parameterised query."]


def test_the_score_takes_the_model_and_the_cross_examiner_from_every_record_not_the_first(
        tmp_path, monkeypatch, capsys):
    """PR 23 produces no findings, so a --from-database round records no model
    against it, and reading records[0] named the harness's default instead of
    the round's model."""
    empty = _round(pr_number=23, diff=_second_diff(), reply=json.dumps({"findings": [], "summary": "Nothing."}))
    empty["model"], empty["cross_model"] = "qwen3.5:9b", None
    full = _round(pr_number=24)
    full["model"], full["cross_model"] = "qwen3.5:9b", "gemma4:12b"
    _ledger(tmp_path, monkeypatch, [_judgement(full["findings"][0])])
    runs = _write(tmp_path, "round1", [empty, full])
    assert P.main(["score", str(runs), "round1"]) == 0
    assert "model qwen3.5:9b with gemma4:12b cross-examining" in capsys.readouterr().out


# ---------------------------------------------------------------- the ledger on the way in


def test_a_ledger_with_one_judge_stops_the_score_instead_of_producing_a_number(tmp_path, monkeypatch, capsys):
    """save_ledger validates before a write, but a ledger can be edited by hand
    or arrive through a merge conflict, so every read validates too."""
    record = _round()
    entry = _judgement(record["findings"][0])
    entry["judges"] = entry["judges"][:1]
    _ledger(tmp_path, monkeypatch, [entry])
    runs = _write(tmp_path, "round1", [record])
    assert P.main(["score", str(runs), "round1"]) == 2
    err = capsys.readouterr().err
    assert "is not valid" in err and "has 1 judges, not exactly two" in err


# ---------------------------------------------------------------- a partial round


def test_the_markdown_row_of_a_partial_round_says_partial_where_the_precision_would_be(
        tmp_path, monkeypatch, capsys):
    """The runbook redirects `score --markdown` straight into docs/, so a row
    over half a ledger has to say so on the row itself."""
    judged = _round(pr_number=24)
    fresh = _round(pr_number=29, diff=_second_diff(), reply=_second_reply())
    _ledger(tmp_path, monkeypatch, [_judgement(judged["findings"][0])])
    runs = _write(tmp_path, "round1", [judged, fresh])
    assert P.main(["score", str(runs), "round1", "--markdown"]) == 2
    out = capsys.readouterr().out
    assert "This round is partial: 1 of its 2 distinct findings are judged" in out
    assert "| round1 | 2 | 2 | 1 | 1 | 0 | partial (1 of 2 judged) |" in out


def test_the_markdown_row_carries_the_tally_and_links_the_protocol(tmp_path, monkeypatch, capsys):
    real = _round(pr_number=24)
    not_real = _round(pr_number=29, diff=_second_diff(), reply=_second_reply())
    _ledger(tmp_path, monkeypatch, [_judgement(real["findings"][0]),
                                    _judgement(not_real["findings"][0], pull_requests=(29,),
                                               verdicts=("not_real", "not_real"),
                                               reasons=("style_preference", "style_preference"))])
    runs = _write(tmp_path, "round1", [real, not_real])
    assert P.main(["score", str(runs), "round1", "--markdown"]) == 0
    out = capsys.readouterr().out
    t = P.tally(P.load_records(str(runs), "round1"), P.load_ledger())
    assert f"| round1 | {t['occurrences']} | {t['distinct']} | {t['judged']} | {t['real']} | {t['disputed']} | 0.50 |" in out
    for row in t["per_pr"]:
        assert f"| {row['pr']} | {row['files']} | {row['findings']} | {row['judged']} | {row['real']} | 1.00 |" in out \
            or f"| {row['pr']} | {row['files']} | {row['findings']} | {row['judged']} | {row['real']} | 0.00 |" in out
    assert "| style preference | 2 |" in out
    assert "[../../PRECISION.md](../../PRECISION.md)" in out, "the row sits two levels under the protocol"


# ---------------------------------------------------------------- a mistyped command line


def test_an_only_that_is_not_a_pull_request_number_is_one_line_and_not_a_traceback(tmp_path, capsys):
    assert P.main(["run", "--out", str(tmp_path / "records"), "--tag", "round1", "--only", "twenty-four"]) == 2
    assert "is not a pull request number" in capsys.readouterr().err
    assert P.main(["run", "--out", str(tmp_path / "records"), "--tag", "round1", "--only", ","]) == 2
    assert "names no pull request" in capsys.readouterr().err


def test_a_ledger_that_is_not_json_is_one_line_and_not_a_traceback(tmp_path, monkeypatch, capsys):
    record = _round()
    path = tmp_path / "judgements.json"
    path.write_text("{ this was hand-edited", encoding="utf-8")
    monkeypatch.setattr(P, "LEDGER", path)
    runs = _write(tmp_path, "round1", [record])
    assert P.main(["score", str(runs), "round1"]) == 2
    assert "precision: " in capsys.readouterr().err


# ---------------------------------------------------------------- one finding, two pull requests


def test_a_finding_seen_on_two_pull_requests_of_one_round_is_recorded_against_both(tmp_path, monkeypatch, capsys):
    first = _round(pr_number=24)
    again = _round(pr_number=29)
    ledger = _ledger(tmp_path, monkeypatch)
    runs = _write(tmp_path, "round1", [first, again])
    rows = P.unjudged(P.load_records(str(runs), "round1"), P.load_ledger())
    assert [prs for _, _, prs in rows] == [[24, 29]], "one fingerprint, both pull requests"
    doc = P.skeleton("round1", rows)
    assert doc["verdicts"][0]["pull_request"] == 24 and doc["verdicts"][0]["pull_requests"] == [24, 29]
    assert P.pull_requests_of({"pull_request": 24}) == [24], "a skeleton written before the list still merges"
    filled = []
    for judge in ("judge-a", "judge-b"):
        theirs = json.loads(json.dumps(doc))
        theirs["judge"], theirs["date"] = judge, "2026-09-12"
        for v in theirs["verdicts"]:
            v["verdict"], v["reason"] = "real", "one line of reason"
        path = tmp_path / f"round1-{judge}.json"
        path.write_text(json.dumps(theirs), encoding="utf-8")
        filled.append(str(path))
    assert P.main(["merge", *filled]) == 0
    assert json.loads(ledger.read_text(encoding="utf-8"))["judgements"][0]["pull_requests"] == [24, 29]


def test_the_fingerprint_of_a_title_forgets_the_kind_inside_a_redaction_marker():
    one = P.fingerprint("a.py", "A committed token [REDACTED:aws-key] in the fixture", "x = 1")
    assert one == P.fingerprint("a.py", "A committed token [REDACTED:github-token] in the fixture", "x = 1")
    assert one == P.fingerprint("a.py", "  a committed  token [REDACTED:other] in the fixture.  ", "x = 1")
    assert one != P.fingerprint("a.py", "A committed token in the fixture", "x = 1")


# ---------------------------------------------------------------- the database guard


def _database(path: Path, rows) -> None:
    """A reviews.db with the columns the harness's own query names."""
    import sqlite3

    conn = sqlite3.connect(path)
    conn.executescript(
        "create table reviews (id text, repository text, pr_number int, head_sha text, status text, model text,"
        " cross_model text, started_at text, duration_seconds real, created_at text);"
        "create table findings (review_id text, path text, line int, category text, severity text, title text,"
        " evidence text, recommendation text, confidence real, source_model text, cross_verdict text,"
        " cross_reason text);")
    for review_id, model, created_at, title in rows:
        conn.execute("insert into reviews values (?, 'Owner/Name', 24, 'b', 'completed', ?, 'gemma4:12b',"
                     " '2026-09-07 22:59:30', 672.4, ?)", (review_id, model, created_at))
        conn.execute("insert into findings values (?, 'app/handler.py', 5, 'security', 'high', ?, ?,"
                     " 'Use a parameterised query.', 0.9, ?, 'real', '')", (review_id, title, QUERY_LINE, model))
    conn.commit()
    conn.close()


def test_only_the_most_recent_completed_review_of_a_pull_request_is_read(tmp_path, capsys):
    """Today each pull request of the set has exactly one completed review. A
    re-review would add a second, and both sets of findings would be read as one
    round's, so the newest by created_at wins and the rest are named."""
    path = tmp_path / "reviews.db"
    _database(path, [("r1", "qwen3.5:9b", "2026-09-07 22:48:11", "The older reading"),
                     ("r2", "qwen4:9b", "2026-09-10 20:01:02", "The newer reading")])
    stored, meta = P.read_database(str(path), "Owner/Name")
    assert [f["title"] for f in stored[24]] == ["The newer reading"]
    assert meta[24]["model"] == "qwen4:9b"
    err = capsys.readouterr().err
    assert "pr 24: 2 completed reviews hold findings" in err and "skipping 1" in err


def test_a_row_that_is_still_in_the_write_ahead_log_is_read_because_the_open_is_not_immutable(tmp_path):
    """The App keeps reviews.db in write-ahead logging mode, and immutable=1
    tells SQLite to ignore the log, so a review written but not yet checkpointed
    was silently not in the round."""
    import sqlite3

    path = tmp_path / "reviews.db"
    _database(path, [("r1", "qwen3.5:9b", "2026-09-07 22:48:11", "Checkpointed")])
    live = sqlite3.connect(path)
    try:
        live.execute("pragma journal_mode=WAL")
        live.execute("insert into reviews values ('r2', 'Owner/Name', 26, 'c', 'completed', 'qwen3.5:9b',"
                     " 'gemma4:12b', '2026-09-07 23:30:00', 60.0, '2026-09-07 23:20:00')")
        live.execute("insert into findings values ('r2', 'app/handler.py', 5, 'security', 'high', 'In the log', ?,"
                     " 'Use a parameterised query.', 0.9, 'qwen3.5:9b', 'real', '')", (QUERY_LINE,))
        live.commit()
        stored, _ = P.read_database(str(path), "Owner/Name")
        assert sorted(stored) == [24, 26], "the row in the write-ahead log is part of the round"
    finally:
        live.close()


# ---------------------------------------------------------------- what a replay can be read over


def test_a_replay_refuses_a_round_that_was_never_fully_judged(tmp_path, monkeypatch, capsys):
    """A replay is read as the change in a number, so the round before it needs
    one: a carried finding nobody judged leaves nothing to compare with."""
    judged = _round(pr_number=24)
    fresh = _round(pr_number=29, diff=_second_diff(), reply=_second_reply())
    _ledger(tmp_path, monkeypatch, [_judgement(judged["findings"][0])])
    runs = _write(tmp_path, "round1", [judged, fresh])
    assert P.main(["replay", str(runs), "round1", "--out", str(tmp_path / "after"),
                   "--tag-out", "round1-after"]) == 2
    err = capsys.readouterr().err
    assert fresh["findings"][0]["fingerprint"] in err
    assert "no number before the change" in err


def test_a_replay_bounds_the_number_over_the_unjudged_findings_and_not_the_new_fingerprints(
        tmp_path, monkeypatch, capsys):
    """The round before is fully judged and the replay brings out two findings
    the round did not have, one of which the ledger already holds from another
    round. The bound is over the one nobody has judged: counting both would put
    a judged finding in the denominator twice."""
    judged_extra = {"category": "quality", "severity": "low", "title": "An import that is not used", "line": 2,
                    "evidence": "import sqlite3", "recommendation": "Delete the import.", "confidence": 0.8}
    unjudged_extra = {"category": "quality", "severity": "low", "title": "The connection is never closed", "line": 6,
                      "evidence": "return sqlite3.connect('app.db').execute(query)",
                      "recommendation": "Close the connection.", "confidence": 0.8}
    sql = json.loads(ONE_FINDING)["findings"][0]
    after_reply = json.dumps({"findings": [sql, judged_extra, unjudged_extra], "summary": "Three."})
    after_round = _round(reply=after_reply)
    by_title = {f["title"]: f for f in after_round["findings"] if f["path"] == "app/handler.py"}
    assert len(by_title) == 3, "all three locate in the diff"
    record = _round()
    handler = next(f for f in record["files"] if f["filename"] == "app/handler.py")
    handler["model_texts"] = [after_reply]
    _ledger(tmp_path, monkeypatch, [
        _judgement(by_title["SQL built by string concatenation"]),
        _judgement(by_title["An import that is not used"], verdicts=("not_real", "not_real"),
                   reasons=("style_preference", "style_preference"))])
    runs = _write(tmp_path, "round1", [record])
    assert P.main(["replay", str(runs), "round1", "--out", str(tmp_path / "after"),
                   "--tag-out", "round1-after"]) == 0
    out = capsys.readouterr().out
    assert "carried 1 fingerprint(s), 0 vanished, 2 new" in out
    assert "1 finding nobody has judged; sheet it" in out
    assert "precision after is between 0.33 and 0.67, against 1.00 before" in out


def test_a_replay_refuses_a_round_recorded_with_the_verify_pass_on(tmp_path, monkeypatch, capsys):
    """A verify reply sits between the reviewer's and the cross-examiner's in
    model_texts, so replaying such a round would hand the cross-examiner the
    verify pass's words. `run` cannot make one any more, and a record from
    before, or from VERIFY_FINDINGS in the environment, is refused."""
    with pytest.raises(SystemExit):
        P.parse_args(["run", "--out", "/tmp/nowhere", "--verify"])
    record = _round()
    record["settings"]["verify_findings"] = True
    _ledger(tmp_path, monkeypatch, [_judgement(record["findings"][0])])
    runs = _write(tmp_path, "round1", [record])
    assert P.main(["replay", str(runs), "round1", "--out", str(tmp_path / "after"),
                   "--tag-out", "round1-after"]) == 2
    assert "ran with VERIFY_FINDINGS on" in capsys.readouterr().err


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")
def test_with_file_context_on_the_file_text_comes_from_the_pull_requests_head(tmp_path):
    """The judged before and after is two run tags, so the on tag has to read the
    file at the head commit of the pull request, the way the App's contents call
    does. Read here from a temporary repository, with git and no model."""
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null", GIT_CONFIG_NOSYSTEM="1")

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(tmp_path), *args],
                       capture_output=True, check=True, env=env)

    git("init", "-b", "main")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "handler.py").write_text(
        "import os\nimport sqlite3\n\ndef handle(request):\n"
        "    query = \"x\"\n    return sqlite3.connect('app.db').execute(query)\n"
        "SENTINEL_FILE_ONLY = 1\n", encoding="utf-8")
    git("add", "app/handler.py")
    git("commit", "-m", "first")
    head = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
                          capture_output=True, check=True, env=env).stdout.decode().strip()
    settings = _settings(file_context=True)
    assert settings.FILE_CONTEXT and settings.FILE_CONTEXT_LINES == 60
    llm = RecordingChatModel(response=ONE_FINDING)
    recorder = P.Recorder()
    llm.callbacks = [recorder]
    reviewer = P.FileReviewer(llm, settings, prompt=P.review_prompt_with_context)
    entry = dict(ENTRY, head_sha=head)
    record = asyncio.run(P.review_pull_request(entry, DIFF, reviewer, recorder, settings,
                                               file_text_for=lambda rev, path: P.file_at(str(tmp_path), rev, path)))
    assert "SENTINEL_FILE_ONLY" in llm.seen_text, "the file at the head reached the model"
    handler = [f for f in record["files"] if f["filename"] == "app/handler.py"][0]
    assert handler["context_mode"] == "whole" and handler["file_redactions"] == 0
    assert record["settings"]["file_context"] is True and record["settings"]["file_context_lines"] == 60
    # the file the temporary repository does not hold simply gets none
    other = [f for f in record["files"] if f["filename"] == "app/util.js"][0]
    assert other["context_mode"] == "unavailable"
